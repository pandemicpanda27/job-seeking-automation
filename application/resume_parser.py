
import os
import re
import pdfplumber
from PyPDF2 import PdfReader
try:
    from docx import Document
except ImportError:
    Document = None

class ResumeParser:
    def __init__(self):
        # Comprehensive skills database with 200+ technologies
        self.skills_database = {
            # Programming Languages
            'Python': ['python', 'py', 'python3'],
            'JavaScript': ['javascript', 'js', 'jsx'],
            'TypeScript': ['typescript', 'ts', 'tsx'],
            'Java': ['java', 'j2ee'],
            'C++': ['c++', 'cpp', 'c plus plus'],
            'C#': ['c#', 'csharp', 'dotnet'],
            'Go': ['golang', 'go'],
            'Rust': ['rust', 'rustlang'],
            'PHP': ['php', 'php7', 'php8'],
            'Ruby': ['ruby', 'rails'],
            'Swift': ['swift'],
            'Kotlin': ['kotlin'],
            'Scala': ['scala'],
            'R': ['r programming', ' r '],
            'MATLAB': ['matlab'],
            'SQL': ['sql', 'tsql', 'pl/sql'],
            'HTML': ['html', 'html5'],
            'CSS': ['css', 'css3', 'scss', 'sass'],
            'Bash': ['bash', 'shell', 'shellscript'],
            'PowerShell': ['powershell'],
            
            # Frontend Frameworks
            'React': ['react', 'reactjs', 'react.js'],
            'Vue.js': ['vue', 'vuejs', 'vue.js'],
            'Angular': ['angular', 'angularjs'],
            'Next.js': ['next.js', 'nextjs', 'next'],
            'Svelte': ['svelte'],
            'Ember': ['ember', 'emberjs'],
            'Backbone': ['backbone.js'],
            'jQuery': ['jquery'],
            'Bootstrap': ['bootstrap'],
            'Tailwind': ['tailwind', 'tailwindcss'],
            'Material-UI': ['material-ui', 'mui'],
            
            # Backend Frameworks
            'Django': ['django'],
            'Flask': ['flask'],
            'FastAPI': ['fastapi'],
            'Spring': ['spring', 'spring boot'],
            'Spring Boot': ['spring boot', 'springboot'],
            'Express.js': ['express', 'expressjs'],
            'Node.js': ['node.js', 'nodejs', 'node'],
            'Laravel': ['laravel'],
            'Symfony': ['symfony'],
            'ASP.NET': ['asp.net', 'asp', 'dotnet'],
            'Ruby on Rails': ['rails', 'ruby on rails'],
            'NestJS': ['nestjs', 'nest.js'],
            'Fastify': ['fastify'],
            'Koa': ['koa'],
            'Tornado': ['tornado'],
            'Bottle': ['bottle'],
            'Pyramid': ['pyramid'],
            
            # Databases
            'MongoDB': ['mongodb', 'mongo'],
            'PostgreSQL': ['postgresql', 'postgres', 'psql'],
            'MySQL': ['mysql', 'mariadb'],
            'Redis': ['redis'],
            'Cassandra': ['cassandra'],
            'DynamoDB': ['dynamodb'],
            'Firebase': ['firebase', 'firestore'],
            'SQL Server': ['sql server', 'mssql', 'sqlserver'],
            'Oracle': ['oracle database', 'oracle'],
            'Elasticsearch': ['elasticsearch', 'elastic'],
            'Neo4j': ['neo4j'],
            'CouchDB': ['couchdb'],
            'RethinkDB': ['rethinkdb'],
            'Memcached': ['memcached'],
            'Solr': ['solr'],
            
            # Cloud Platforms
            'AWS': ['aws', 'amazon web services', 'amazon'],
            'Azure': ['azure', 'microsoft azure'],
            'Google Cloud': ['gcp', 'google cloud', 'google cloud platform'],
            'DigitalOcean': ['digitalocean', 'digital ocean'],
            'Heroku': ['heroku'],
            'IBM Cloud': ['ibm cloud'],
            'Oracle Cloud': ['oracle cloud'],
            'Alibaba Cloud': ['alibaba cloud'],
            
            # DevOps & Infrastructure
            'Docker': ['docker', 'dockerfile'],
            'Kubernetes': ['kubernetes', 'k8s', 'k3s'],
            'Jenkins': ['jenkins'],
            'GitLab CI': ['gitlab ci', 'gitlab-ci'],
            'GitHub Actions': ['github actions'],
            'CircleCI': ['circleci'],
            'Travis CI': ['travis ci'],
            'Terraform': ['terraform'],
            'Ansible': ['ansible'],
            'Chef': ['chef'],
            'Puppet': ['puppet'],
            'Vagrant': ['vagrant'],
            'nginx': ['nginx', 'ngninx'],
            'Apache': ['apache', 'httpd'],
            'IIS': ['iis', 'internet information services'],
            
            # Version Control
            'Git': ['git'],
            'GitHub': ['github', 'gh'],
            'GitLab': ['gitlab'],
            'Bitbucket': ['bitbucket'],
            'SVN': ['subversion', 'svn'],
            'Mercurial': ['mercurial', 'hg'],
            
            # AI/ML
            'Machine Learning': ['machine learning', 'ml', 'ml/ai'],
            'Deep Learning': ['deep learning', 'dl'],
            'TensorFlow': ['tensorflow'],
            'PyTorch': ['pytorch', 'torch'],
            'Keras': ['keras'],
            'Scikit-learn': ['scikit-learn', 'sklearn'],
            'Pandas': ['pandas'],
            'NumPy': ['numpy', 'np'],
            'SciPy': ['scipy'],
            'Matplotlib': ['matplotlib'],
            'Seaborn': ['seaborn'],
            'OpenCV': ['opencv', 'cv2'],
            'NLP': ['nlp', 'natural language processing'],
            'Computer Vision': ['computer vision', 'cv'],
            'Hugging Face': ['hugging face', 'transformers'],
            'XGBoost': ['xgboost'],
            'LightGBM': ['lightgbm'],
            'CatBoost': ['catboost'],
            
            # APIs & Protocols
            'REST API': ['rest api', 'rest', 'restful'],
            'GraphQL': ['graphql'],
            'gRPC': ['grpc'],
            'SOAP': ['soap'],
            'WebSocket': ['websocket', 'ws'],
            'OAuth': ['oauth', 'oauth2'],
            'JWT': ['jwt', 'json web token'],
            
            # Testing
            'Jest': ['jest'],
            'Mocha': ['mocha'],
            'Jasmine': ['jasmine'],
            'Pytest': ['pytest'],
            'unittest': ['unittest'],
            'Selenium': ['selenium'],
            'Cypress': ['cypress'],
            'RSpec': ['rspec'],
            'JUnit': ['junit'],
            'TestNG': ['testng'],
            
            # Monitoring & Logging
            'Prometheus': ['prometheus'],
            'Grafana': ['grafana'],
            'ELK Stack': ['elk stack', 'elk'],
            'Splunk': ['splunk'],
            'Datadog': ['datadog'],
            'New Relic': ['new relic'],
            'Sentry': ['sentry'],
            'CloudWatch': ['cloudwatch'],
            
            # Message Queues
            'RabbitMQ': ['rabbitmq', 'rabbit'],
            'Kafka': ['kafka'],
            'ActiveMQ': ['activemq'],
            'AWS SQS': ['sqs', 'aws sqs'],
            'AWS SNS': ['sns', 'aws sns'],
            'Pub/Sub': ['pubsub', 'pub/sub'],
            
            # Other Tools
            'Linux': ['linux', 'ubuntu', 'debian', 'centos', 'rhel'],
            'Windows': ['windows', 'windows server'],
            'macOS': ['macos', 'mac os'],
            'Agile': ['agile'],
            'Scrum': ['scrum'],
            'Kanban': ['kanban'],
            'JIRA': ['jira'],
            'Confluence': ['confluence'],
            'Slack': ['slack'],
            'Docker Compose': ['docker compose', 'docker-compose'],
            'Minikube': ['minikube'],
            'Helm': ['helm'],
            'ArgoCD': ['argocd'],
            'REST': ['rest', 'restful api'],
            'MicroServices': ['microservices', 'microservice'],
            'CI/CD': ['ci/cd', 'cicd', 'continuous integration'],
        }
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF using pdfplumber"""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
        except Exception as e:
            print(f"Error extracting from pdfplumber: {e}")
            # Fallback to PyPDF2
            try:
                with open(pdf_path, 'rb') as file:
                    reader = PdfReader(file)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
            except:
                pass
        return text
    
    def extract_text_from_docx(self, docx_path):
        """Extract text from DOCX file"""
        if Document is None:
            return ""
        try:
            doc = Document(docx_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
            return text
        except Exception as e:
            print(f"Error extracting from DOCX: {e}")
            return ""
    
    def extract_text_from_txt(self, txt_path):
        """Extract text from TXT file"""
        try:
            with open(txt_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error extracting from TXT: {e}")
            return ""
    
    def extract_text(self, file_path):
        """Extract text from any supported file format"""
        if file_path.lower().endswith('.pdf'):
            return self.extract_text_from_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            return self.extract_text_from_docx(file_path)
        elif file_path.lower().endswith('.txt'):
            return self.extract_text_from_txt(file_path)
        return ""
    
    def extract_skills(self, text):
        """Extract ALL skills from text"""
        skills_found = set()
        text_lower = text.lower()
        
        for skill, aliases in self.skills_database.items():
            for alias in aliases:
                # Use word boundaries to avoid partial matches
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, text_lower):
                    skills_found.add(skill)
                    break
        
        return sorted(list(skills_found))
    
    def extract_experience(self, text):
        """Extract experience - handles months and years accurately"""
        text_lower = text.lower()
        
        # Patterns to match experience with word boundaries
        patterns = [
            (r'(\d+)\s*(?:months?|mo\.?)\s*(?:of\s+)?(?:experience|exp\.?|exp\b)', 'months'),
            (r'(\d+)\s*(?:years?|yrs?\.?)\s*(?:of\s+)?(?:experience|exp\.?|exp\b)', 'years'),
            (r'experience\s*[:\-]?\s*(\d+)\s*(?:months?|mo\.?)', 'months'),
            (r'experience\s*[:\-]?\s*(\d+)\s*(?:years?|yrs?\.?)', 'years'),
            (r'(\d+)\s*months?\s+of\s+(?:professional\s+)?experience', 'months'),
            (r'(\d+)\s*years?\s+of\s+(?:professional\s+)?experience', 'years'),
            (r'exp\.?\s*[:\-]?\s*(\d+)\s*(?:months?|mo\.?)', 'months'),
            (r'exp\.?\s*[:\-]?\s*(\d+)\s*(?:years?|yrs?\.?)', 'years'),
        ]
        
        for pattern, unit in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                value = matches[0]
                return f"{value} {unit}"
        
        return "Not specified"
    
    def extract_name(self, text):
        """Extract name from resume"""
        lines = text.split('\n')
        for line in lines[:10]:
            line = line.strip()
            if line and 2 <= len(line) <= 50:
                # Check if it looks like a name (capital letters, no special chars)
                if all(c.isalpha() or c.isspace() for c in line):
                    if len(line.split()) <= 4:
                        return line
        return "Professional"
    
    def categorize_role(self, skills):
        """Categorize job role based on skills"""
        if not skills:
            return "Software Developer"
        
        skills_lower = [s.lower() for s in skills]
        
        # ML Engineer
        if any(keyword in skills_lower for keyword in ['machine learning', 'deep learning', 'tensorflow', 'pytorch', 'nlp', 'computer vision']):
            return "ML Engineer"
        
        # Frontend Developer
        if any(keyword in skills_lower for keyword in ['react', 'vue.js', 'angular', 'typescript', 'frontend']):
            return "Frontend Developer"
        
        # Backend Developer
        if any(keyword in skills_lower for keyword in ['django', 'flask', 'fastapi', 'spring', 'node.js', 'express.js', 'laravel']):
            return "Backend Developer"
        
        # Full Stack Developer
        if sum(1 for keyword in skills_lower if any(x in keyword for x in ['react', 'vue', 'angular', 'node', 'django', 'flask', 'spring'])) >= 2:
            return "Full Stack Developer"
        
        # DevOps Engineer
        if any(keyword in skills_lower for keyword in ['docker', 'kubernetes', 'aws', 'azure', 'ci/cd', 'terraform', 'ansible']):
            return "DevOps Engineer"
        
        # Data Engineer
        if any(keyword in skills_lower for keyword in ['hadoop', 'spark', 'kafka', 'sql', 'etl', 'data']):
            return "Data Engineer"
        
        # Data Scientist
        if any(keyword in skills_lower for keyword in ['machine learning', 'pandas', 'scikit-learn', 'data science']):
            return "Data Scientist"
        
        return "Software Developer"
    
    def parse(self, file_path):
        """Parse resume and extract all information"""
        try:
            # Extract text
            text = self.extract_text(file_path)
            
            if not text or len(text.strip()) < 10:
                return {
                    'name': 'Professional',
                    'category': 'Software Developer',
                    'experience': 'Not specified',
                    'skills': [],
                    'error': 'Could not extract sufficient text from file'
                }
            
            # Extract information
            skills = self.extract_skills(text)
            experience = self.extract_experience(text)
            name = self.extract_name(text)
            category = self.categorize_role(skills)
            
            return {
                'name': name,
                'category': category,
                'experience': experience,
                'skills': skills,
                'error': None
            }
        except Exception as e:
            return {
                'name': 'Professional',
                'category': 'Software Developer',
                'experience': 'Not specified',
                'skills': [],
                'error': f'Error parsing resume: {str(e)}'
            }
