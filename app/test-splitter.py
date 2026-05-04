from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken
from transformers import AutoTokenizer

text = """
Teghime, c'est ce col qui permet aux Bastiais d'aller d'est
en ouest. Les gens disent qu'arrivé là-haut, on peut contem-
pler « les deux mers ». Bizarrerie de l'homme fidèle à ses
lieux qui modèle son espace à sa manière: la Méditerranée
est une seule mer, mais Teghime la divise en deux et invente
ainsi la Tyrrhénienne.
Comme dans bien des cas, le col constitue ici la limite d'un
territoire. Celui des Bastiacci, des Villesi ou des Cardinchi
qui se dépaysent dès qu'ils le franchissent.
Teghime est une limite haute. Hauts plateaux des ber-
gers qui mettaient et mettent toujours en synergie la plaine,
la ville et la montagne. Par exemple, en allant de Subigna à
la Serra di Pignu et en vendant leurs produits au marché de
Bastia. Bergers hauts en couleurs dans la lignée de Filidatu et
Filimonda, héros bucoliques de l'écrivain Sébastien Dalzeto,
familier de ces lieux comme l' indique son pseudonyme.
Teghime, c'est aussi l'accès aux « nivere » , ces superbes
lieux de stockage de la neige qui, transformée en glace, était
ramenée à la ville afin de rafraîchir les familles les plus aisées.
Par l'aménagement de ces glacières en pierres et ardoises
équipées d'un puits à neige, les hommes, depuis l'Antiquité,
cherchent à retenir un peu l'hiver. E nivere ! Lieux devenus
mythiques.
Mais Teghime, c'est aussi une image moins idyllique:
celle de la décharge publique de Bastia jusqu'à la fin du
xx• siècle. Le lieu symbolique de bien des débats sur l' éco-
logie, de la question des déchets à l'opportunité (ou l'op-
portunisme) des éoliennes.
En tout cas, s'il y a une chose qui ne doit pas terminer
dans les poubelles de l'histoire, c'est l'épisode de 1943.
Tout d'abord les lieux investis par plus de deux milliers
d'italiens errants pris dans l'étau d'une guerre finissante et
d'une paix non encore aboutie. Triste ironie du sort pour ces
pauvres soldats tentant une fuite par l'ouest. Ils furent blo-
qués après Teghime, traqués d'un côté par les Allemands, sans
être del' autre dans le camp des Alliés.
Mais le fait majeur de Teghime arrivera quelques mois
après, en octobre 1943. Les goumiers marocains franchirent
Teghime dans leurs djellabas de grosse laine brune qui leur
servaient de couverture, de tenue de camouflage et éventuel-
lement de linceul. Ils vainquirent au col, et la Corse fut libé-
rée à Bastia le 4 octobre 1943. Pourrons-nous oublier le sang
de la libération de la Corse sur les djellabas ?
Aujourd'hui, Teghime est la promenade favorite des
Bastiais qui vont, en guise de glacière, « se manger une glace
à Saint-Florent». Pour autant, Teghime restera à jamais un
lieu de partage: partage des saisons, de la mer, des terres, de la
mémoire et, bien sûr, de la parole et del' image par les ondes."""


print(f"taille: {len(text)} caractères")

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2400,
    chunk_overlap=20,
    length_function=len,
    is_separator_regex=False,
)
texts = text_splitter.create_documents([text])
tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-Instruct-v0.2")
print(f"{len(texts)} morceaux")
for i,text in enumerate(texts):
    tokens = tokenizer.tokenize(text.page_content)
    print(f"Texte {i+1}: {len(tokens) + 2} tokens")

