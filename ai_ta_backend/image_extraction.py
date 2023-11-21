import os
import fitz
from docx import Document
from pptx import Presentation
from tempfile import NamedTemporaryFile

def extract_images_from_pdf(pdf_doc, s3_path):
    """
    Extracts images from a pdf file and stores them in a folder.
    """
    print("Extracting images from pdf...")

    try:
        filename = s3_path.split("/")[-1]
        course_name = s3_path.split("/")[-2]
        # check for images directory
        image_dir = "extracted_images"
        folder_name = "images_from_" + filename 
        print("folder name: ", folder_name)

        if not os.path.exists(image_dir):
            print("Creating directory for extracted images...")
            os.makedirs(image_dir)
        
        if not os.path.exists(os.path.join(image_dir, folder_name)):
            print("Creating directory for extracted images from this pdf...")
            os.makedirs(os.path.join(image_dir, folder_name))
        folder_path = os.path.join(image_dir, folder_name)

        for i in range(len(pdf_doc)):
            for img in pdf_doc.get_page_images(i):
                xref = img[0]
                base = os.path.splitext(pdf_doc.name)[0]
                pix = fitz.Pixmap(pdf_doc, xref)
                if pix.n < 5:
                    pix.save(os.path.join(folder_path, "page%s-%s.png" % (i, xref)))
                else:
                    pix1 = fitz.Pixmap(fitz.csRGB, pix)
                    pix1.save(os.path.join(folder_path, "page%s-%s.png" % (i, xref)))
                    pix1 = None
                pix = None
        return "Success!" 
    except Exception as e:
        return "Error extracting images from pdf: " + str(e)