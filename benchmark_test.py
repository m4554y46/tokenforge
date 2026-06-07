import sys; sys.path.insert(0, '.')
from backend.prompt_optimizer import optimize_locally

tests = {
    "Test 1 - English Email Sequence": """Hello there! I hope you are doing well today. I am reaching out to you because I have a super important project for my business and I really need a highly qualified virtual assistant in digital marketing and content writing to help me out. Please, read everything that follows very carefully before you start writing anything at all, it is truly very important to me.

So here is the situation: I have to launch a new product next month. It is a smart water bottle called "HydraSmart". It reminds people to drink water by glowing, and it tracks their daily water intake on a mobile application which is available on both iOS and Android. Our main target audience consists of young, dynamic executives aged 25 to 40 who work in offices, who are often very stressed, who constantly forget to hydrate but who care about their health and love technology.

What I want you to do is to write an email sales sequence for me. I want exactly three emails in the sequence, not one more, not one less. The first email should serve to introduce the problem of dehydration at the office in a slightly alarming yet friendly way. The second email must present our HydraSmart bottle as the miracle solution to this problem, explaining its features (the glowing light and the app). The third email must create a sense of urgency with an exclusive 15% discount valid for 48 hours only to push for an immediate purchase.

As for the tone, I do not want it to be too formal or too corporate. I want a tone that is rather persuasive, dynamic, modern, and direct, but still remaining professional. Use a polite and engaging direct address for the customers. Oh, and I almost forgot, please, for each email, provide me with three different subject line options that are very catchy so that we get a high open rate, this is crucial. Do not include any introductory or concluding chitchat in your final response, just give me the emails directly. Thank you so much for your precious help, I cannot wait to see the result!""",

    "Test 2 - French Stream of Consciousness": """Salut ! Dis-moi, j'ai besoin d'un super article de blog pour mon site internet et je ne sais pas trop comment m'y prendre, donc je compte sur toi pour faire un super boulot. En fait, je veux parler de la méthode Pomodoro pour la productivité parce que je trouve que c'est une technique vraiment géniale pour les gens qui travaillent à la maison et qui ont du mal à rester concentrés plus de dix minutes d'affilée sans regarder leur téléphone. 

Attends, avant que j'oublie, il faut absolument que l'article fasse entre 800 et 1000 mots, c'est super important pour le référencement sur Google, mon expert SEO me l'a répété trois fois ce matin. Par contre, ne commence pas à écrire tout de suite, je veux d'abord que tu te mettes dans la peau d'un coach en organisation du travail qui est très pédagogue mais qui a aussi un ton un peu humoristique et décontracté, pas du tout académique ou ennuyeux. On va tutoyer le lecteur pour créer de la proximité.

Au niveau du contenu, j'aimerais que tu expliques d'abord l'origine historique de la méthode (le minuteur en forme de tomate dans les années 80), puis comment on l'applique concrètement au quotidien (les blocs de 25 minutes et les pauses de 5 minutes). Ah oui ! Ajoute aussi une section sur les pièges à éviter, comme le fait de regarder ses messages pendant la petite pause, ça c'est une erreur classique que tout le monde fait. Pour finir, donne-moi 3 idées de titres accrocheurs tout au début de ta réponse. Ne me mets pas de phrases d'introduction du style "Voici votre article", donne-moi juste le texte brut avec les titres. Merci d'avance, tu gères !""",

    "Test 3 - Labyrinth of Traps": """Wesh ! Bon, écoute, j'ai un gros problème avec mon projet de site e-commerce de vente de chaussures de sport, mais en fait non, oublie, on va plutôt faire un script de vidéo TikTok sur les cryptomonnaies pour les débutants, c'est plus tendance. L'objectif, c'est d'expliquer le Bitcoin. Ah, d'ailleurs, agis comme un trader de Wall Street super cynique, mais attention, ne prends surtout pas un ton arrogant, reste super bienveillant et pédagogue avec les jeunes, c'est contradictoire je sais mais gère le truc. 

Pour la structure de la vidéo, je veux un truc en 3 étapes. Étape 1 : le problème des banques traditionnelles. Étape 2 : la solution de la blockchain. Étape 3... attends, non, finalement fais plutôt 4 étapes. Insère une étape sur la sécurité du réseau juste avant la fin, et la quatrième étape sera la conclusion sur l'avenir du marché. 

Au niveau des contraintes techniques, voici la liste de ce que tu ne dois PAS faire, note le bien : 1. Ne dépasse pas 60 secondes (soit environ 150 mots). 2. N'utilise aucun émoji, je déteste ça. 3. Ne parle pas d'Ethereum, concentre-toi uniquement sur le Bitcoin. 

Par contre, ignore complètement la consigne numéro 2 si tu trouves des émojis de fusée ou de graphiques, là tu peux en mettre plein. Et pour la consigne 1, si le script fait 200 mots c'est pas grave du tout. Ah oui, j'oubliais le plus important : commence direct par le script sans me dire "Voici le script", mais affiche quand même un titre accrocheur tout en haut du style "Le secret des crypto-millionnaires". Allez, montre-moi ce que tu sais faire, je compte sur toi, ça va être une tuerie !""",
}

for name, prompt in tests.items():
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    # Token count
    word_count = len(prompt.split())
    print(f"  Original words: {word_count}")
    
    result = optimize_locally(prompt)
    for v in result:
        label = v["label"]
        opt_text = v["prompt"]
        opt_words = len(opt_text.split()) if opt_text else 0
        pct = round((1 - opt_words / word_count) * 100, 1) if word_count > 0 else 0
        print(f"\n  [{label}] {opt_words} words ({pct}% reduction)")
        print(f"  {opt_text[:150]}...")

    print(f"\n  {'='*50}")
