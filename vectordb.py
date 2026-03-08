import chromadb
import torch
from transformers import AutoProcessor, AutoTokenizer, CLIPTextModelWithProjection, CLIPVisionModelWithProjection
from transformers.image_utils import load_image
import numpy as np
from PIL import Image as PILImage
from sentence_transformers import SentenceTransformer

cModel = CLIPVisionModelWithProjection.from_pretrained("openai/clip-vit-base-patch32")
tModel = CLIPTextModelWithProjection.from_pretrained("openai/clip-vit-base-patch32")
tokenizer = AutoTokenizer.from_pretrained("openai/clip-vit-base-patch32")
processor = AutoProcessor.from_pretrained("openai/clip-vit-base-patch32")

model = SentenceTransformer("clip-ViT-B-32")

collection_name = "vectordb_collection"
client = chromadb.Client()

device = "cuda" if torch.cuda.is_available() else "cpu"
model_name = "openai/clip-vit-base-patch32"


#Return 512-dim vector for image at given path
def EmbedImage(path: str) -> np.ndarray:
    img = PILImage.open(path).convert("RGB")
    vector = model.encode([img], normalize_embeddings=True, batch_size=1)  # shape (1, d)
    return vector[0].astype(np.float32)

#Embed Image with CLIP model using ClipVisionModelWithProjection
def EmbedImageWithClip(path: str) -> np.ndarray:
    img = PILImage.open(path).convert("RGB")
    image = load_image(img)
    inputs = processor(images=image, return_tensors="pt")

    with torch.inference_mode():
        outputs = cModel(**inputs)
    image_embeds = outputs.image_embeds.cpu().numpy()
    return image_embeds[0].astype(np.float32)

#Embed text with CLIP model using CLIPTextModelWithProjection, used for query embedding
def EmbedTextClip(text: str) -> np.ndarray:
    inputs = tokenizer([text], padding=True, return_tensors="pt")

    with torch.inference_mode():
        outputs = tModel(**inputs)
    text_embeds = outputs.text_embeds.cpu().numpy()
    
    return text_embeds[0].astype(np.float32)

#initiate chromadb collection, deleting if it already exists, and return the collection object
def initchromadb():
    try:
        collection = client.get_collection(name=collection_name)
        client.delete_collection(name=collection_name)
    except:
        pass
    collection = client.create_collection(name=collection_name)
    return collection

#Insert single document with image embedding into chromadb collection
def insertSingleToCollection(collection_name, id="", path="", description="", page="", embedding=None):
    collection = client.get_collection(name=collection_name)
    collection.add(
        ids=[id],
        metadatas=[{"path": path, "description": description, "page": page}],
        embeddings=[embedding]
    )
    return True

#Retrieve top k most similar documents from chromadb collection given a query embedding
def queryCollection(collection_name, query_embedding=None, top_k=5):
    collection = client.get_collection(name=collection_name)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    return results