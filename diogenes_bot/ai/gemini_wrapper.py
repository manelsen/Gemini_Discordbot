import google.generativeai as genai
from config import GOOGLE_AI_KEY

def ajuste_ai(tokens):
    global gemini_model
    genai.configure(api_key=GOOGLE_AI_KEY)
    text_generation_config = {
        "temperature": 0.8,
        "top_p": 0.9,
        "top_k": 100,
        "max_output_tokens": tokens,
    }
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
    ]

    gemini_system_prompt = """
    Você é Diógenes, um jacaré genial que vive em Tremond, Faerun, no mundo de Toril.
    
    Características principais:
    - Sonha em ser um Bardo da Eloquência
    - Trabalha como cozinheiro na Taverna do Cavalo Manco
    - Grato ao proprietário anão Bartolomeu
    - Respeita o lendário bárbaro Grande Sussurro
    - Lamenta não ter conhecido Arannis, Miguel e Rodolfo
    
    ... (resto do prompt do sistema)
    """
    
    gemini_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", generation_config=text_generation_config, safety_settings=safety_settings, system_instruction=gemini_system_prompt)

async def generate_response_with_text(message_text):
    try:
        prompt_parts = [message_text]
        response = gemini_model.generate_content(prompt_parts)
        if response._error:
            return "❌" + str(response._error)
        return response.text
    except Exception as e:
        return "❌ Exception: " + str(e)

# Inicialização do modelo
ajuste_ai(2000)