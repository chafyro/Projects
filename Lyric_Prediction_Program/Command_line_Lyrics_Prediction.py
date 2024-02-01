import argparse
import pickle

#
parser = argparse.ArgumentParser()
parser.add_argument('-f', '--file', help='path to the song lyrics to predict')
parser.add_argument('-w', '--write', help='song line to predict')
args = parser.parse_args()

with open('trained_model.pkl', 'rb') as pickle_file:
    model = pickle.load(pickle_file)

#
def predict_artist(text, model=model):
    processed_text = ' '.join(tokenize_lemmatize(text.lower()))
    features = vectorizer.transform([processed_text])
    predicted_artist = model.predict(features)
    return predicted_artist[0]


if args.file:
    with open(args.file, 'r') as lyrics_file:
        lyrics = lyrics_file.read()
        predicted_artist = predict_artist(lyrics)
        print("Predicted Artist:", predicted_artist)

if args.write:
    predicted_artist = predict_artist(args.write)
    print("Predicted Artist:", predicted_artist)
