import re
import nltk
import pandas as pd
import os
from pdfminer.high_level import extract_text

# Regex patterns
PHONE_REG = re.compile(r'[\+\(]?[1-9][0-9 .\-\(\)]{8,}[0-9]')
EMAIL_REG = re.compile(r'[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+')

# Ensure required NLTK resources are available
for resource in ['corpora/stopwords', 'tokenizers/punkt']:
    try:
        nltk.data.find(resource)
    except LookupError:
        nltk.download(resource.split('/')[-1], quiet=True)

STOP_WORDS = set(nltk.corpus.stopwords.words('english'))

def load_skills_from_excel(file_path: str) -> set:
    if not os.path.exists(file_path):
        print(f"Skills file not found at {file_path}")
        return set()

    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return set()

    skills = set()
    for row in df.itertuples(index=False):
        for cell in row:
            if pd.notnull(cell):
                for skill in str(cell).split(','):
                    cleaned = skill.strip().lower()
                    if cleaned:
                        skills.add(cleaned)
    return skills

class ResumeParser:
    def __init__(self, skills_db: set):
        self.skills_db = skills_db

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        if not os.path.exists(pdf_path):
            print(f"PDF file not found at {pdf_path}")
            return ""
        try:
            return extract_text(pdf_path)
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""

    def extract_phone_number(self, resume_text: str) -> str or None:
        phone = re.findall(PHONE_REG, resume_text)
        if phone:
            number = ''.join(phone[0])
            if resume_text.find(number) >= 0 and len(number) < 16:
                return number
        return None

    def extract_emails(self, resume_text: str) -> list:
        return re.findall(EMAIL_REG, resume_text)

    def extract_skills(self, input_text: str) -> set:
        word_tokens = nltk.tokenize.word_tokenize(input_text.lower())
        filtered_tokens = [
            w for w in word_tokens
            if w not in STOP_WORDS and any(c.isalnum() for c in w)
        ]
        ngrams = list(map(' '.join, nltk.everygrams(filtered_tokens, 2, 4)))

        found_skills = set()
        for token in filtered_tokens:
            if token in self.skills_db:
                found_skills.add(token)
        for ngram in ngrams:
            if ngram in self.skills_db:
                found_skills.add(ngram)

        return found_skills

    def parse_resume(self, pdf_path: str) -> dict:
        if not os.path.exists(pdf_path):
            print(f"Cannot parse. File does not exist: {pdf_path}")
            return {
                "Email": None,
                "Phone": None,
                "Skills": set()
            }

        resume_text = self.extract_text_from_pdf(pdf_path)
        if not resume_text:
            print("No text extracted from resume.")
            return {
                "Email": None,
                "Phone": None,
                "Skills": set()
            }

        emails = self.extract_emails(resume_text)
        phone = self.extract_phone_number(resume_text)
        skills = self.extract_skills(resume_text)

        print("Resume parsed successfully.")
        return {
            "Email": emails[0] if emails else None,
            "Phone": phone,
            "Skills": skills
        }

# Optional CLI test
if __name__ == '__main__':
    SKILLS_FILE = 'skills_dataset.xlsx'
    RESUME_FILE = 'resume.pdf'

    print(f"Loading skills from {SKILLS_FILE}...")
    SKILLS_DB = load_skills_from_excel(SKILLS_FILE)

    if not SKILLS_DB:
        print("Could not load skills. Exiting.")
    else:
        print("Initializing Resume Parser...")
        parser = ResumeParser(SKILLS_DB)

        print(f"Parsing resume: {RESUME_FILE}...")
        results = parser.parse_resume(RESUME_FILE)

        print("\n" + "="*30)
        print("     RESUME PARSING RESULTS")
        print("="*30)
        print(f"Email: {results['Email'] if results['Email'] else 'Email not found'}")
        print(f"Phone: {results['Phone'] if results['Phone'] else 'Phone not found'}")
        print(f"Skills: {results['Skills']}")
        print("="*30)
