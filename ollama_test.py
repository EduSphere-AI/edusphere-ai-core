from utils.ollama_translator import OllamaTranslator

translator = OllamaTranslator(model='mistral')
result = translator.translate_text("Hello, how are you?", "hi")
print(result)