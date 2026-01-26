import requests
import json
import logging
from typing import List, Dict, Optional
import time

logger = logging.getLogger(__name__)

class OllamaTranslator:
    """Translate using local Ollama models"""
    
    LANGUAGE_NAMES = {
        'hi': 'Hindi',
        'ta': 'Tamil',
        'te': 'Telugu',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'mr': 'Marathi',
        'gu': 'Gujarati',
        'bn': 'Bengali',
        'pa': 'Punjabi',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh-CN': 'Chinese (Simplified)',
        'zh-TW': 'Chinese (Traditional)',
        'ar': 'Arabic',
    }
    
    def __init__(self, model: str = 'mistral', base_url: str = 'http://127.0.0.1:11434'):
        """
        Initialize Ollama Translator
        
        Args:
            model: Model name (mistral, neural-chat, llama2, etc.)
            base_url: Ollama server URL
        """
        self.model = model
        self.base_url = base_url
        self.timeout = 120  # 2 minutes timeout for translation
        
        # Test connection
        if not self._test_connection():
            logger.warning(f"Could not connect to Ollama at {base_url}")
        else:
            logger.info(f"Connected to Ollama. Using model: {model}")
    
    def _test_connection(self) -> bool:
        """Test if Ollama server is running"""
        try:
            response = requests.get(f'{self.base_url}/api/tags', timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return False
    
    def translate_text(self, text: str, target_lang: str = 'hi') -> str:
        """
        Translate text to target language using Ollama
        
        Args:
            text: Text to translate
            target_lang: Language code (e.g., 'hi', 'ta', 'es')
            
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        lang_name = self.LANGUAGE_NAMES.get(target_lang, target_lang)
        
        # Create prompt for translation
        prompt = f"""Translate the following English text to {lang_name}. 
Only output the translated text, nothing else. Do not include any explanation or notes.

English: {text}

{lang_name}:"""
        
        try:
            response = requests.post(
                f'{self.base_url}/api/generate',
                json={
                    'model': self.model,
                    'prompt': prompt,
                    'stream': False,
                    'temperature': 0.3  # Low temperature for consistent translation
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                translated = result.get('response', text).strip()
                logger.debug(f"Translated to {lang_name}")
                return translated
            else:
                logger.error(f"Ollama returned status {response.status_code}")
                return text
                
        except requests.exceptions.Timeout:
            logger.error(f"Translation timeout after {self.timeout}s")
            return text
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text
    
    def translate_list(self, texts: List[str], target_lang: str = 'hi') -> List[str]:
        """Translate multiple texts"""
        translated = []
        for i, text in enumerate(texts):
            logger.info(f"Translating item {i+1}/{len(texts)}")
            translated.append(self.translate_text(text, target_lang))
        return translated
    
    def translate_dict(self, data: Dict, target_lang: str = 'hi', 
                       keys_to_translate: Optional[List[str]] = None) -> Dict:
        """
        Translate specific keys in dictionary
        
        Args:
            data: Dictionary to translate
            target_lang: Target language code
            keys_to_translate: List of keys to translate (if None, translates all string values)
        """
        translated_data = {}
        
        for key, value in data.items():
            if keys_to_translate and key not in keys_to_translate:
                translated_data[key] = value
            elif isinstance(value, str):
                translated_data[key] = self.translate_text(value, target_lang)
            elif isinstance(value, dict):
                translated_data[key] = self.translate_dict(value, target_lang, keys_to_translate)
            elif isinstance(value, list):
                translated_data[key] = [
                    self.translate_text(item, target_lang) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                translated_data[key] = value
        
        return translated_data
    
    def translate_slides(self, slides: List[Dict], target_lang: str = 'hi') -> List[Dict]:
        """Translate slides content"""
        translated_slides = []
        
        for i, slide in enumerate(slides):
            logger.info(f"Translating slide {i+1}/{len(slides)}")
            translated_slide = {}
            
            for key, value in slide.items():
                if isinstance(value, str):
                    translated_slide[key] = self.translate_text(value, target_lang)
                elif isinstance(value, list):
                    translated_slide[key] = self.translate_list(value, target_lang)
                else:
                    translated_slide[key] = value
            
            translated_slides.append(translated_slide)
        
        return translated_slides