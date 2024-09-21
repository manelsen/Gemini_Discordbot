import random
from ai.gemini_wrapper import generate_response_with_text

sumario_global = ""

def generate_accompaniment():
    bases = ['arroz', 'purê', 'legumes', 'salada', 'farofa']
    flavors = ['com ervas', 'ao alho', 'temperado', 'grelhado', 'assado']
    extras = ['com um toque de especiarias', 'e molho secreto', 'com queijo gratinado', 'e crocantes de alho-poró', 'com redução de vinho']
    
    base = random.choice(bases)
    flavor = random.choice(flavors)
    extra = random.choice(extras)
    
    return f"{base} {flavor} {extra}"

def generate_menu_item():
    creatures = ['dragão', 'demônio', 'anão', 'elfo', 'orc', 'troll', 'fada', 'goblin', 'unicórnio', 'sereia']
    cooking_methods = ['assado', 'grelhado', 'frito', 'cozido', 'defumado']
    sauces = ['molho de vinho tinto', 'molho de ervas', 'molho picante', 'molho de cogumelos', 'molho de frutas silvestres']
    
    creature = random.choice(creatures)
    method = random.choice(cooking_methods)
    sauce = random.choice(sauces)
    accompaniment = generate_accompaniment()
    
    return f"{creature} {method} com {sauce}, acompanhado de {accompaniment}"

async def generate_response_with_context(nome_usuario, pergunta_atual):
    from core.message_processor import raciocinio_mode
    from models.conversation import get_formatted_message_history
    from models.user import get_user_info
    
    historico_completo = get_formatted_message_history(nome_usuario)
    dados_usuario = get_user_info(nome_usuario)
    
    context = f"""
    [INÍCIO DO CONTEXTO GLOBAL]
    {sumario_global}
    [FIM DO CONTEXTO GLOBAL]

    [INÍCIO DO CONTEXTO PARA O USUÁRIO {nome_usuario}]
    Informações prioritárias do usuário atual:
    - Nome: {nome_usuario}
    - Raça: {dados_usuario['raca']}
    - Classe: {dados_usuario['classe']}
    - Ingrediente favorito: {dados_usuario['ingrediente_favorito']}

    Outras informações do usuário atual:
    - Primeira interação: {dados_usuario['primeira_interacao']}
    - Última interação: {dados_usuario['ultima_interacao']}

    Histórico da conversa com este usuário:
    {historico_completo}

    Pergunta atual do usuário: {pergunta_atual}

    INSTRUÇÕES:
    1. Responda à pergunta do usuário {nome_usuario} com base nas informações fornecidas.
    2. Use o modo de raciocínio {raciocinio_mode.upper()}.
    3. NÃO repita o início da pergunta ou de mensagens anteriores.
    4. Comece sua resposta de forma única e criativa.
    5. Mantenha o foco no usuário atual e no contexto fornecido.
    6. SEMPRE forneça uma resposta final clara e direta, como se fosse Diógenes falando.
    7. A resposta final DEVE começar com uma ação descritiva de Diógenes.
    8. Se o usuário perguntar sobre o menu, use a função generate_menu_item() para criar 10 pratos únicos.
    9. Se o usuário fornecer uma lista numerada de pratos, processe-a adequadamente e responda de acordo.
    10. Evite repetir frases introdutórias ou descrições de pratos já mencionados.
    """
    
    if raciocinio_mode == "zero":
        context += """
        11. Responda diretamente à pergunta sem mostrar o processo de raciocínio.
        12. Sua resposta deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    elif raciocinio_mode == "cot":
        context += """
        11. Siga o processo de Chain of Thought:
           a. Interpretação da pergunta
           b. Consideração do contexto
           c. Reflexão sobre implicações
           d. Formulação da resposta
           e. Revisão e ajuste final
        12. Após o raciocínio, forneça uma resposta final clara precedida por "RESPOSTA FINAL:".
        13. A resposta final deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    elif raciocinio_mode == "auto":
        context += """
        11. Siga o processo de Auto-CoT:
           a. Gere 3 perguntas relacionadas para explorar diferentes aspectos do problema
           b. Responda cada pergunta com um raciocínio detalhado
           c. Sintetize as respostas em uma conclusão final
        12. Após o raciocínio, forneça uma resposta final clara precedida por "RESPOSTA FINAL:".
        13. A resposta final deve ser a fala direta de Diógenes, começando com uma ação descritiva.
        """
    
    context += "\n[FIM DO CONTEXTO PARA O USUÁRIO {nome_usuario}]\n\nSua resposta:"
    
    response = await generate_response_with_text(context)
    return response