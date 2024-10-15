import openai

OPENAI_API_KEY = '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'
openai.api_key = OPENAI_API_KEY

def get_chatgpt_response(prompt):
    response = openai.ChatCompletion.create(
        model='gpt-4',
        messages=[
            {'role': 'system', 'content': 'You are a game master for a fantasy role-playing game.'},
            {'role': 'user', 'content': prompt}
        ],
        max_tokens=150,
        n=1,
        stop=None,
        temperature=0.7,
    )
    message = response.choices[0].message.content.strip()
    return message