import PyPDF2
import fitz  # PyMuPDF
import re
from pathlib import Path
import concurrent.futures
import streamlit as st
import shutil
import zipfile
import os
# import subprocess


# Set the environment variables for Streamlit
os.environ["STREAMLIT_SERVER_ENABLE_CORS"] = "true"
os.environ["STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION"] = "false"

# Start the Streamlit app
# subprocess.run(["streamlit", "run", "app.py", "--server.port=8501"])

def find_id_pages(input_pdf):
    doc = fitz.open(input_pdf)
    id_pages = []
    id_pattern = re.compile(r'\(ID#:\s*(\d+)\)')

    for i, page in enumerate(doc):
        text = page.get_text()
        if id_pattern.search(text):
            id_pages.append(i)

    return id_pages

def split_pdf(input_pdf, output_folder, progress_callback):
    input_path = Path(input_pdf)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Find pages with IDs
    id_pages = find_id_pages(input_pdf)
    
    if not id_pages:
        st.error("No ID pages found in the PDF.")
        return

    pdf_reader = PyPDF2.PdfReader(str(input_path))
    total_pages = len(pdf_reader.pages)
    temp_pdfs = []

    for i in range(len(id_pages)):
        start_page = id_pages[i]
        end_page = id_pages[i + 1] if i + 1 < len(id_pages) else total_pages

        pdf_writer = PyPDF2.PdfWriter()
        for j in range(start_page, end_page):
            pdf_writer.add_page(pdf_reader.pages[j])
        
        temp_pdf_path = output_folder / f'temp_{i}.pdf'
        with open(temp_pdf_path, 'wb') as output_pdf:
            pdf_writer.write(output_pdf)
        
        temp_pdfs.append(temp_pdf_path)
        progress_callback((i + 1) / len(id_pages))  # Update progress bar

    # Process renaming in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(lambda pdf_path: extract_and_rename_pdf(pdf_path, output_folder), temp_pdfs)

def extract_and_rename_pdf(pdf_path, output_folder):
    doc = fitz.open(pdf_path)
    text_first_page = doc[0].get_text()
    
    # Extract ID using a regex pattern for the format (ID#: 31323)
    match_first_page = re.search(r'\(ID#:\s*(\d+)\)', text_first_page)
    
    if match_first_page:
        id_value = match_first_page.group(1)
        new_pdf_path = output_folder / f'{id_value}.pdf'
        pdf_path.rename(new_pdf_path)
    else:
        new_pdf_path = output_folder / f'unknown_{pdf_path.stem}.pdf'
        pdf_path.rename(new_pdf_path)

def zip_output_folder(output_folder, zip_name):
    shutil.make_archive(zip_name, 'zip', output_folder)

def clean_up(output_folder, zip_name):
    shutil.rmtree(output_folder)
    os.remove(f"{zip_name}.zip")

# Streamlit App Portion
st.title("PDF Splitter and Renamer")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
# output_folder = st.text_input("Output Folder", "output_pdfs")
output_folder = "output_folder"

if st.button("Split and Rename PDF"):
    if uploaded_file and output_folder:
        try:
            # Save uploaded file temporarily
            with open("temp_input.pdf", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            progress_bar = st.progress(0)
            def update_progress(progress):
                progress_bar.progress(progress)
            
            split_pdf("temp_input.pdf", output_folder, update_progress)
            
            zip_name = "output_pdfs"
            zip_output_folder(output_folder, zip_name)
            st.success("PDF split and renamed successfully!")
            
            with open(f"{zip_name}.zip", "rb") as f:
                st.download_button(
                    label="Download ZIP",
                    data=f,
                    file_name=f"{zip_name}.zip",
                    mime="application/zip"
                )
            
            # Remove temporary file
            Path("temp_input.pdf").unlink()
            clean_up(output_folder, zip_name)
        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.error("Please upload a PDF file and specify an output folder.")
