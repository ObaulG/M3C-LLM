import re
from collections import defaultdict

# voir https://hal.science/hal-01108063/document

word_positions = defaultdict(list)  # Déclaré globalement pour l'exemple

def preprocess(text):
    # Minuscules + suppression ponctuation + segmentation
    text = re.sub(r'[^\w\s]', '', text.lower())
    return text.split()

def find_common_sequences(text1, text2, min_sequence_length=3):
    # Étape 1 : Prétraitement et intersection avec positions
    words1 = preprocess(text1)
    words2 = preprocess(text2)

    # Indexer les positions de chaque mot dans text2
    for pos, word in enumerate(words2):
        word_positions[word].append(pos)

    # Trouver les mots communs avec leurs positions dans text1
    common_words = []
    for pos, word in enumerate(words1):
        if word in word_positions:
            common_words.append((pos, word, word_positions[word]))

    return words1, common_words

def detect_copy_paste_sequences(text1, text2, min_sequence_length=3):
    words1, common_words = find_common_sequences(text1, text2)
    print(common_words)
    print(word_positions)
    sequences = []
    i = 0
    n = len(common_words)

    while i < n:
        # Étape 2 : Fenêtre glissante pour construire les séquences
        start_i = i
        current_sequence = [common_words[start_i][1]]  # Mot initial
        current_positions = common_words[start_i][2]   # Positions dans text2

        # Étendre la séquence tant que possible
        j = start_i + 1
        while j < n:
            print("current sequence: ", current_sequence)
            next_word = common_words[j][1]
            print("next word: ", next_word)
            # Vérifier si le mot suivant dans text1 existe juste après dans text2
            next_pos_in_text2 = [p for p in word_positions[next_word] if p > current_positions[-1]]
            if next_pos_in_text2:
                current_sequence.append(next_word)
                current_positions = next_pos_in_text2
                print(current_sequence)
                j += 1
            else:
                break

        # Étape 3 : Sauvegarder si la séquence est assez longue
        if len(current_sequence) >= min_sequence_length:
            sequences.append({
                "sequence": " ".join(current_sequence),
                "start_pos_text1": common_words[start_i][0],
                "end_pos_text1": common_words[j-1][0],
                "length": len(current_sequence)
            })
            i = j  # Sauter les mots déjà traités
        else:
            i += 1

    return sequences

if __name__ == "__main__":
    # Exemple d'utilisation
    document = """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer id elementum neque. Donec ultrices congue velit ut ullamcorper. Aenean sodales orci eget commodo finibus. Curabitur libero leo, interdum sed felis rhoncus, hendrerit vestibulum nunc. Vivamus at viverra nibh, at iaculis est. Nulla nec feugiat lectus. Nulla lacinia hendrerit blandit. Vivamus quis odio molestie sem auctor auctor. Duis ornare lacus sapien, ut posuere neque vehicula id. Vivamus viverra semper semper. Praesent mattis sodales elit at tempor. Maecenas auctor malesuada lorem, sed lacinia quam placerat ut. Maecenas eu nunc vestibulum, aliquet nulla mollis, iaculis dui.

Duis vel nisl a dolor pulvinar tincidunt. Quisque placerat eget metus sit amet dignissim. Aliquam erat volutpat. Aliquam luctus ut sapien eu dictum. Aliquam ac leo vel sapien efficitur consequat. Duis vel tempor magna. Ut ac sem venenatis nunc sagittis ultricies. Nulla fermentum rhoncus erat in varius. Nulla eget maximus turpis. Aliquam volutpat, purus non semper vehicula, orci sapien tincidunt nibh, sed aliquam arcu velit eu odio. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas.

Sed nisi massa, lacinia in justo et, tempus sagittis elit. Duis vitae velit ac nisl cursus porttitor et eu leo. Fusce ut consequat dui, a aliquet est. Curabitur faucibus fermentum erat quis condimentum. Aenean ac ligula neque. Etiam odio lacus, dignissim ac tellus vel, volutpat tempor augue. Donec placerat, neque vel lobortis tempor, ex felis dictum lectus, vel lobortis dolor dui quis lectus. Integer nec finibus urna. Aenean nibh neque, congue sed libero in, iaculis faucibus felis. Phasellus viverra nec sem at maximus. Suspendisse sollicitudin sodales sapien ut consequat. Suspendisse consectetur sodales pellentesque. Cras faucibus commodo ex sed dapibus. Sed vel lorem nec mauris rhoncus suscipit. Cras ac tempor ligula, nec placerat ex.

Nullam suscipit vehicula est, sit amet rhoncus enim lacinia et. Curabitur sit amet leo eros. Aliquam feugiat aliquam dolor. In magna lorem, ornare sit amet nulla dignissim, fermentum faucibus magna. Duis id iaculis ipsum, sit amet sollicitudin risus. Aenean eu nibh leo. Vestibulum ac rutrum nunc. Nulla pulvinar odio id dolor finibus efficitur. Donec consectetur lobortis vehicula. Duis dignissim ipsum diam, at tincidunt lorem consectetur et. Donec placerat elit nec odio aliquet, in pulvinar leo tincidunt. In at euismod velit. Duis euismod vehicula diam, et hendrerit magna cursus vel. Cras blandit metus eu neque venenatis, nec semper dui euismod. Vestibulum commodo semper odio, eu tristique massa laoreet id."""
    user_response = "Nullam suscipit vehicula est, sit amet rhoncus enim lacinia et. Curabitur sit amet leo eros. Aliquam feugiat aliquam dolor. In magna lorem, ornare sit amet nulla dignissim, fermentum faucibus magna. Duis id iaculis ipsum, sit amet sollicitudin risus. Aenean eu nibh leo. Vestibulum ac rutrum nunc. Nulla pulvinar odio id dolor finibus efficitur. Donec consectetur lobortis vehicula. Duis dignissim ipsum diam, at tincidunt lorem consectetur et. Donec placerat elit nec odio aliquet, in pulvinar leo tincidunt. In at euismod velit. Duis euismod vehicula diam, et hendrerit magna cursus vel. Cras blandit metus eu neque venenatis, nec semper dui euismod. Vestibulum commodo semper odio, eu tristique massa laoreet id."

    _, common_words = find_common_sequences(document, user_response)
    sequences = detect_copy_paste_sequences(document, user_response, min_sequence_length=3)

    print("Séquences copiées détectées :", sequences)
