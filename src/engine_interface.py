"""Chunk processor engine interface"""

import re

from launch_setup import settings
from socket_messages import SocketTranscriptMessage, SocketErrorMessage

class EngineNotFound(Exception):
    """Exception thrown when ASR engine was unknown"""

class ModelNotFound(Exception):
    """Exception thrown when model does not exist"""

class EngineInterface():
    """Interface for chunk processor engines"""
    def __init__(self, send_message = None, options: dict = None):
        # Message and state
        self.send_message = send_message
        self.accept_chunks = True
        self.is_open = True

        # Common options and defaults
        if not options:
            options = {}
        # -- almost all engines work with 16khz mono
        self._sample_rate = options.get("samplerate", float(16000))
        # -- "de-DE", "en-US", etc. (could be: "de_DE", "de", ...)
        self._language = options.get("language")
        if self._language:
            self._language = self._language.replace("_", "-")  # make sure we have xx-XX format
            self.language_code_short = re.split("[-]", self._language)[0].lower()
        else:
            self.language_code_short = None
        # -- model name
        self._asr_model_name = options.get("model", None)
        # -- model folder/file relative to: settings.asr_models_folder
        self._asr_model_path = ""
        # -- model parameters
        self._asr_model_properties = []
        # -- send final result once after stop event
        self._continuous_mode = options.get("continuous", False)
        # -- use text processors to optimize final result
        self._optimize_final_result = options.get("optimizeFinalResult", False)

        # Validate model
        model_index = 0
        if self._asr_model_name:
            if self._asr_model_name in settings.asr_model_names:
                # Reset language etc. because model has higher priority
                model_index = settings.asr_model_names.index(self._asr_model_name)
            else:
                # Given model not found
                raise ModelNotFound(f"ASR model name unknown: '{self._asr_model_name}'")
        elif self._language and self._language in settings.asr_model_languages:
            # Use first model that fits language
            model_index = settings.asr_model_languages.index(self._language)
        elif self._language and self.language_code_short:
            # Take the first model that has the same basic language
            base_lang_fit = [l for l in settings.asr_model_languages
                if l.startswith(self.language_code_short)]
            if base_lang_fit:
                model_index = settings.asr_model_languages.index(base_lang_fit[0])
            else:
                # Model not found
                raise ModelNotFound(f"No ASR model for language: {self.language_code_short}")
        else:
            # No given model or language -> Just take the first one available
            model_index = 0
        # adapt other parameters
        self._language = settings.asr_model_languages[model_index]
        self._asr_model_path = settings.asr_model_paths[model_index]
        self._asr_model_properties = settings.asr_model_properties[model_index]

    async def process(self, chunk: bytes):
        """Process chunk"""
    async def finish_processing(self):
        """Block new process requests, wait for last process to finish and send result"""
    async def close(self):
        """Close and clean up"""
    def get_options(self):
        """Return possible options as object (optionally) with defaults"""
        return {}

    async def send_transcript(self,
        transcript, is_final = False, confidence = -1, features = None, alternatives = None):
        """Send transcript result"""
        if self.send_message is not None:
            msg = SocketTranscriptMessage(
                transcript, is_final, confidence, features, alternatives)
            await self.send_message(msg)

    async def on_before_close(self):
        """Run before close for any required extra action"""
        self.is_open = False

    async def on_error(self, error_message):
        """Send error message"""
        self.accept_chunks = False
        if self.send_message is not None:
            await self.send_message(
                SocketErrorMessage(500, "AsrEngineError", error_message))
