from app import create_app
from extensions import db
from models import Question
import logging
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_questions():
    questions = [
        {
            'text': 'Please select your top Business Initiatives in Cloud Security',
            'question_type': 'multiple_choice',
            'options': [
                {
                    'title': 'Cloud Adoption and Business Alignment',
                    'description': 'Ensure cloud adoption supports overall business objectives by leveraging SentinelOne\'s Unified Visibility and Secrets Scanning to maintain security and compliance.',
                    'icon': 'align-center'
                },
                {
                    'title': 'Achieving Key Business Outcomes',
                    'description': 'Use SentinelOne\'s Offensive Security Engine to drive business outcomes by proactively identifying and mitigating risks that impact service delivery.',
                    'icon': 'target'
                },
                {
                    'title': 'Maximizing ROI for Cloud Security',
                    'description': 'Optimize return on investment with SentinelOne\'s AI-Powered Threat Detection and Response, ensuring efficient use of resources and effective risk mitigation.',
                    'icon': 'trending-up'
                },
                {
                    'title': 'Integration of Cloud Security with Business Strategy',
                    'description': 'Align cloud security goals with broader IT and business strategies using SentinelOne\'s Unified Platform and Data Lake for centralized and streamlined security management.',
                    'icon': 'git-merge'
                },
                {
                    'title': 'Driving Innovation and Value Delivery',
                    'description': 'Leverage SentinelOne\'s Offensive Security Engine and Verified Exploit Paths™ to enable innovation while reducing vulnerabilities, thereby ensuring a secure environment for business initiatives.',
                    'icon': 'zap'
                },
                {
                    'title': 'Supporting Digital Transformation',
                    'description': 'Enhance digital transformation initiatives by utilizing SentinelOne\'s Agentless and Agent-Based Capabilities, ensuring robust security across diverse cloud environments.',
                    'icon': 'refresh-cw'
                },
                {
                    'title': 'Balancing Rapid Adoption with Compliance',
                    'description': 'Maintain a balance between rapid cloud adoption and strong security by using SentinelOne\'s Secrets Scanning and Cloud Workload Security to mitigate risks while staying compliant.',
                    'icon': 'shield'
                }
            ],
            'required': True,
            'validation_rules': {'min_count': 1, 'max_count': 3},
            'order': 1
        }
    ]

    try:
        # First clear existing questions
        Question.query.delete()
        db.session.commit()
        
        # Add new questions
        for q_data in questions:
            q = Question(
                text=q_data['text'],
                question_type=q_data['question_type'],
                options=q_data.get('options'),
                required=q_data.get('required', True),
                validation_rules=q_data.get('validation_rules', {}),
                order=q_data.get('order', 0)
            )
            db.session.add(q)
        
        db.session.commit()
        logger.info("Questions initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing questions: {e}")
        db.session.rollback()
        raise

def clear_and_init_db():
    try:
        # Drop tables using SQLAlchemy text()
        db.session.execute(text('DROP TABLE IF EXISTS response CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS presentation CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS question CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS "user" CASCADE'))
        db.session.commit()
        
        # Create fresh tables
        db.create_all()
        # Initialize questions
        init_questions()
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        clear_and_init_db()
