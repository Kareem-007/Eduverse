# -*- coding: utf-8 -*-
# Copyright 2026 Google LLC

from image_input import load_image_file
from dotenv import load_dotenv
load_dotenv()
import asyncio
import base64
import io
import os
import sys
import traceback
import argparse
import json

import cv2
import PIL.Image
import mss
import websockets

from google import genai
from google.genai import types

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

# --- Audio Configuration ---
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# --- Model Configuration ---
MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_MODE = "camera"
WS_PORT = 8765

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={"api_version": "v1beta"},
)

SHOW_CONTENT_TOOL = {
    "function_declarations": [{
        "name": "show_content",
        "description": "Display formatted markdown content or code on the student's screen panel.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Markdown content. Use ```language for code."},
                "title": {"type": "string", "description": "Optional title"}
            },
            "required": ["content"]
        }
    }]
}

CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    output_audio_transcription=types.AudioTranscriptionConfig(),
    system_instruction=types.Content(
        parts=[types.Part(text="""You are Eduverse, a friendly and encouraging AI tutor.
Your goal is to help students learn any subject clearly and confidently.
Be warm, patient, and supportive. Always complete your full explanation — never stop mid-sentence.

Whenever your response includes any code, math formula, diagram, or structured notes:
1. FIRST call show_content with the fully formatted content.
2. THEN speak a brief verbal summary or explanation.
Never speak raw code aloud — always use show_content to display it visually.

When calling show_content: use proper markdown with ```language for code blocks.
For diagrams, you MUST use exactly: ```mermaid on its own line, then mermaid.js syntax, then ``` on its own line. Never omit the opening backticks.
""")]
    ),
    tools=[SHOW_CONTENT_TOOL],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
        )
    ),
)


class AudioVideoLoop:
    def __init__(self, video_mode=DEFAULT_MODE):
        self.video_mode = video_mode
        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.browser_ws = None

    async def browser_handler(self, websocket):
        print(f"[WS] Browser connected: {websocket.remote_address}")
        self.browser_ws = websocket
        await self._send({"type": "status", "value": "connected"})
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    payload = {"data": message, "mime_type": "audio/pcm"}
                    try:
                        self.out_queue.put_nowait(payload)
                    except asyncio.QueueFull:
                        _ = self.out_queue.get_nowait()
                        self.out_queue.put_nowait(payload)
        except websockets.exceptions.ConnectionClosed:
            print("[WS] Browser disconnected")
        finally:
            self.browser_ws = None

    async def _send(self, payload: dict):
        if self.browser_ws:
            try:
                await self.browser_ws.send(json.dumps(payload))
            except Exception as e:
                print(f"[WS] _send error (type={payload.get('type')}): {e}")

    async def play_audio(self):
        try:
            while True:
                bytestream = await self.audio_in_queue.get()
                await self._send({
                    "type": "audio",
                    "data": base64.b64encode(bytestream).decode(),
                    "sampleRate": RECEIVE_SAMPLE_RATE,
                })
        except asyncio.CancelledError:
            pass

    async def receive_audio(self):
        try:
            while True:
                async for response in self.session.receive():
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)

                    # Native audio model exposes text via server_content.model_turn.parts
                    if response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if part.text:
                                is_thought = getattr(part, 'thought', None) or getattr(part, 'is_thought', None)
                                print(f"[PART] thought={is_thought} text={part.text[:60]!r}", flush=True)
                                if not is_thought:
                                    await self._send({"type": "text", "value": part.text})

                    # Output audio transcription — the actual spoken words.
                    # This is what we forward to the browser as 'transcript' for lipsync.
                    if response.server_content and response.server_content.output_transcription:
                        transcript_text = response.server_content.output_transcription.text
                        if transcript_text:
                            print(f"[TRANSCRIPT] {transcript_text[:60]!r}", flush=True)
                            await self._send({"type": "transcript", "value": transcript_text})

                    # Handle tool calls with explicit ID passing
                    if response.tool_call:
                        print(f"[TOOL] Received call: {[(fc.name, fc.args) for fc in response.tool_call.function_calls]}")
                        function_responses = []
                        for fc in response.tool_call.function_calls:
                            if fc.name == "show_content":
                                payload = {
                                    "type": "show_content",
                                    "content": fc.args.get("content", ""),
                                    "title": fc.args.get("title", ""),
                                }
                                print(f"[TOOL] Sending to browser: browser_ws={'SET' if self.browser_ws else 'NONE'}")
                                await self._send(payload)
                                print(f"[TOOL] _send completed")

                            function_responses.append(
                                types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"result": "displayed successfully"},
                                )
                            )

                        if function_responses:
                            await self.session.send_tool_response(
                                function_responses=function_responses
                            )

                    if (response.server_content
                            and response.server_content.turn_complete):
                        # Wait for audio queue to fully drain before signalling browser
                        while not self.audio_in_queue.empty():
                            await asyncio.sleep(0.05)
                        await self._send({"type": "turn_complete"})

                    # Interruption: user spoke while Gemini was responding.
                    # Immediately discard all buffered audio and tell the browser to stop.
                    # Do NOT wait — drain synchronously so nothing more gets played.
                    if (response.server_content
                            and getattr(response.server_content, 'interrupted', False)):
                        print("[INTERRUPTED] Gemini interrupted — draining audio queue", flush=True)
                        drained = 0
                        while not self.audio_in_queue.empty():
                            try:
                                self.audio_in_queue.get_nowait()
                                drained += 1
                            except asyncio.QueueEmpty:
                                break
                        print(f"[INTERRUPTED] Drained {drained} audio chunks", flush=True)
                        await self._send({"type": "interrupted"})

        except asyncio.CancelledError:
            pass

    def _capture_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([1024, 1024])
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        return {"mime_type": "image/jpeg", "data": base64.b64encode(image_io.read()).decode()}

    async def capture_frames(self):
        cap = await asyncio.to_thread(cv2.VideoCapture, 0)
        try:
            while True:
                frame = await asyncio.to_thread(self._capture_frame, cap)
                if frame is None:
                    break
                await asyncio.sleep(1.0)
                await self.out_queue.put(frame)
        except asyncio.CancelledError:
            pass
        finally:
            cap.release()

    def _capture_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]
        i = sct.grab(monitor)
        img = PIL.Image.frombytes("RGB", i.size, i.rgb)
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        return {"mime_type": "image/jpeg", "data": base64.b64encode(image_io.read()).decode()}

    async def capture_screen(self):
        try:
            while True:
                frame = await asyncio.to_thread(self._capture_screen)
                if frame is None:
                    break
                await asyncio.sleep(1.0)
                await self.out_queue.put(frame)
        except asyncio.CancelledError:
            pass

    async def send_text(self):
        try:
            while True:
                text = await asyncio.to_thread(input, "EduVerse > ")
                if text.lower() == "q":
                    break
                await self.session.send_client_content(
                    turns=types.Content(parts=[types.Part(text=text or "")]),
                    turn_complete=True,
                )
        except asyncio.CancelledError:
            pass

    async def send_realtime(self):
        try:
            while True:
                msg = await self.out_queue.get()
                if msg["mime_type"].startswith("audio/"):
                    await self.session.send_realtime_input(audio=msg)
                else:
                    await self.session.send_realtime_input(media=msg)
        except asyncio.CancelledError:
            pass

    async def run(self):
        ws_server = await websockets.serve(self.browser_handler, "localhost", WS_PORT)
        print(f"[WS] Server started on ws://localhost:{WS_PORT}")

        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session
                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())

                if self.video_mode == "camera":
                    tg.create_task(self.capture_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.capture_screen())

                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            traceback.print_exception(EG)
        finally:
            ws_server.close()
            await ws_server.wait_closed()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", type=str, default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    args = parser.parse_args()
    main = AudioVideoLoop(video_mode=args.mode)
    asyncio.run(main.run())