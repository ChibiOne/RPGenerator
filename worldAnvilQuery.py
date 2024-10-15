import requests

WORLD_ANVIL_API_KEY = 'YTkCnVGsp4Z922uQpMwerLmLhrPGTatiKSQ4pjuYTuJl5mudKndBUkCyapRY9qzcM5t5Jf1vVQl0SlIiXqQy7DqUvrIZ8xjHe39jdULm5FpgaenBBbTCLPhlVpohrqeNmTQ3of1QFPD6W1Acil38hUOeFxhRs9Ran0NrhnIqr3UULGX24F1b25aap5XHU2BlA48HutcaBck1Qf1uSSc1CJ7AmRA8JzuhqUjLVi1ZnRWSmnN5mFch56Q0Ij'
WORLD_ANVIL_BASE_URL = 'https://www.worldanvil.com/api/boromir'

def get_article(article_id):
    headers = {
        'Authorization': f'Bearer {WORLD_ANVIL_API_KEY}'
    }
    response = requests.get(f'{WORLD_ANVIL_BASE_URL}/article/{article_id}', headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Error fetching article: {response.status_code}')
        return None