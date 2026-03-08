import requests
import os
import base64
import sys
from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import Text, Image, Table, CompositeElement, Title
from unstructured.staging.base import elements_to_json
from vectordb import *
from NemotronNano import *



IMG_DIR = r"extracted/images"
IMAGES = []

os.environ["UNSTRUCTURED_HI_RES_MODEL_NAME"] = "yolox"


#Helper function to get category of unstructured element, returns class name if category not found
def get_category(el):
    return getattr(el, "category", el.__class__.__name__)

#Helper function to get page number from unstructured element metadata, returns None if not found
def get_page(el):
    return getattr(getattr(el, "metadata", None), "page_number", None)


#Extract images from PDF and get their embeddings, along with page number for context, using unstructured
#Returns list of dicts with keys "path", "page", and "embedding"
def ExtractPictures(filename):
    print(f"Extracting pictures from: {filename}")
    image_text_elements = partition_pdf(
    filename=filename,                 
    strategy="hi_res",    
    hi_res_model_name="yolox",
    extract_images_in_pdf=True,                            
    extract_image_block_types=["Image", "Table"],          
    extract_image_block_to_payload=False,
    extract_image_block_output_dir=IMG_DIR
    )

    images_with_pages = []

    for e in image_text_elements:
        is_img = isinstance(e, Image) or isinstance(e, Table) #Show both image and tables
        if is_img:
            md = getattr(e, "metadata", None)
            if md:
                image_path = getattr(md, "image_path", None)
                if image_path:
                    imgembed = EmbedImageWithClip(image_path)
                    images_with_pages.append({
                        "page": get_page(e),
                        "path": image_path,
                        "embedding": imgembed
                    })

    print(f"Test: {images_with_pages[0]['page']}, {images_with_pages[0]['path']}, {images_with_pages[0]['embedding']}")
    return images_with_pages
    

#Adding description to each list of images extracted from each page,
def GetImageDescriptionsFromLLMHelper(ListImagePath):
    DescForEachImage = []
    for docs in ListImagePath:
        for doc in docs:
            clean_res = GetImageDescriptionsFromLLM(doc['path'])
            DescForEachImage.append({
                "path": doc['path'],
                "page": doc['page'],
                "embedding": doc['embedding'],
                "description": clean_res
            })
    return DescForEachImage

#Call NemotronNano with image path to get description of image, which will be used as metadata in 
#vector database at insertion
def GetImageDescriptionsFromLLM(path):
    res = chat_with_media(invoke_url, [path], query, stream=False)
    return res.json()["choices"][0]['message']['content']

#Iterate through list of documents with image paths, get descriptions from LLM, and
#insert into vector database with description as metadata along with page number and image embedding       
def InsertIntoVDB(documents, collection_name):
    id_start = 1
    for doc in documents:
        insertSingleToCollection(collection_name, id=f"img_{id_start}", path=doc['path'], description=doc['description'], page=doc['page'], embedding=doc['embedding'])
        id_start += 1

#For top ranked result, generate response to user query based on description and page number of the image
def GenerateResponseToQuery(results, query):
    path = results['metadatas'][0][0]['path']
    description = results['metadatas'][0][0]['description']
    page = results['metadatas'][0][0]['page']

    CombinedPrompt = f"Based on the following image description: {description}, and the fact that it was found on page {page} of the document, answer the following question: {query}"

    res = chat_with_media(invoke_url, [], CombinedPrompt, stream=False)
    print(path)
    print(res.json()["choices"][0]['message']['content'])
    return res.json()["choices"][0]['message']['content']


#Example terminal command:
#python file.py "[insert query(this query currently does nothing)]" "file_path.pdf"
#python visiondemo.py "Explain images in page 9" "data/grace-blackwell-datasheet.pdf"
if __name__ == "__main__":
    sample_query = sys.argv[1] #Query
    media_samples = list(sys.argv[2:]) #filepath to extract
    print(media_samples)
    
    vecdb = initchromadb()
    print(f"Initialized vector database: {vecdb}")

    documents = []
    for filename in media_samples:
        documents.append(ExtractPictures(filename))

    #Test
    # print(documents)
    # t = EmbedImage(documents[0][0]['path'])
    # print(t)
    # t2 = EmbedImageWithClip(documents[0][0]['path'])

    docWithDesc = GetImageDescriptionsFromLLMHelper(documents)
    InsertIntoVDB(docWithDesc, collection_name)

    query = "What is the Total Memory Bandwidth of GB200 NVL72?"
    query_embedding = EmbedTextClip(query)
    search_results = queryCollection(collection_name, query_embedding=query_embedding, top_k=5)
    print("Search results from vector database:")
    print(search_results)
    te = GenerateResponseToQuery(search_results, query)