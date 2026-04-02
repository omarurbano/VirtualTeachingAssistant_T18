import requests
import os
import base64
import sys
import logging
import time
from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import Text, Image, Table, CompositeElement, Title
from unstructured.staging.base import elements_to_json
from pathlib import Path
from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from vectordb import *
from NemotronNano import *



IMG_DIR = r"extracted/images"
OUT_DIR = Path.cwd() / "figures"
IMAGE_RESOLUTION_SCALE = 2.0
_log = logging.getLogger(__name__)
IMAGES = []

os.environ["UNSTRUCTURED_HI_RES_MODEL_NAME"] = "yolox"

vs = VisionModel()

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

    # print(f"Test: {images_with_pages[0]['page']}, {images_with_pages[0]['path']}, {images_with_pages[0]['embedding']}")
    return images_with_pages

def ExtractImagesWithDocling(path):
    logging.basicConfig(level=logging.INFO)
    #getting path of the pdf file
    data_folder = str(Path(__file__).parent)
    input_doc_path = data_folder + "/" + str(Path(path))
    output_dir = Path(OUT_DIR)

    pipeline_options = PdfPipelineOptions()
    pipeline_options.images_scale = IMAGE_RESOLUTION_SCALE
    pipeline_options.generate_page_images = True
    pipeline_options.generate_picture_images = True

    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    start_time = time.time()
    conv_res = doc_converter.convert(input_doc_path)

    output_dir.mkdir(parents=True, exist_ok=True)
    doc_filename = conv_res.input.file.stem
    # Save images of figures and tables
    pages_with_img = []
    table_counter = 0
    picture_counter = 0
    for element, _level in conv_res.document.iterate_items():
        if isinstance(element, TableItem):
            table_counter += 1
            p = element.prov[0].page_no if element.prov else None
            element_image_filename = (
                output_dir / f"table-{table_counter}-{p}.png"
            )
            with element_image_filename.open("wb") as fp:
                element.get_image(conv_res.document).save(fp, "PNG")
                # img_embed = EmbedImageWithClip(element_image_filename)
                
                pages_with_img.append({"page": f"{p}", "path": f"{element_image_filename}", "embedding": img_embed})

        if isinstance(element, PictureItem):
            picture_counter += 1
            p = element.prov[0].page_no if element.prov else None
            element_image_filename = (
                output_dir / f"figure-{picture_counter}-{p}.png"
            )
            with element_image_filename.open("wb") as fp:
                element.get_image(conv_res.document).save(fp, "PNG")
                img_embed = EmbedImageWithClip(element_image_filename)
                pages_with_img.append({"page": f"{p}", "path": f"{element_image_filename}", "embedding": img_embed})


    end_time = time.time() - start_time
    _log.info(f"Document converted and figures exported in {end_time:.2f} seconds.")
    # print(pages_with_img)
    return pages_with_img

#Adding description to each list of images extracted from each page,
def GetImageDescriptionsFromLLMHelper(ListImagePath):
    DescForEachImage = []
    for docs in ListImagePath:
        for doc in docs:
            clean_res = vs.GetSingleImgDesc(doc['path'])
            DescForEachImage.append({
                "path": doc['path'],
                "page": doc['page'],
                "embedding": doc['embedding'],
                "description": clean_res
            })
    return DescForEachImage



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

    # res = chat_with_media(invoke_url, [], CombinedPrompt, stream=False)
    res = vs.chat_with_media_helper([], CombinedPrompt, stream=False)
    print("\n")
    print(f"Image from {path}, on page {page} of the document")
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
        # documents.append(ExtractImagesWithDocling(filename))
   
    # Test
    # print(documents)
    # t = EmbedImage(documents[0][0]['path'])
    # print(t)
    # t2 = EmbedImageWithClip(documents[0][0]['path'])
    ##########
    docWithDesc = GetImageDescriptionsFromLLMHelper(documents)
    print(docWithDesc)
    InsertIntoVDB(docWithDesc, collection_name)

    # query = "What is the Total Memory Bandwidth of GB200 NVL72?"
    query_embedding = EmbedTextClip(sample_query)
    search_results = queryCollection(collection_name, query_embedding=query_embedding, top_k=5)
    print("Search results from vector database:")
    print(search_results)
    te = GenerateResponseToQuery(search_results, sample_query)
    print(sample_query)