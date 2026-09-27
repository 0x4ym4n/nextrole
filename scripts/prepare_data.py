"""Collect public job feeds, or generate explicitly synthetic developer fixtures.

No private database, account, cookie, or candidate data is used.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ['Python', 'Go', 'Java', 'JavaScript', 'TypeScript', 'React', 'Flutter', 'Dart', 'SQL', 'PostgreSQL', 'Docker', 'Kubernetes', 'AWS', 'Figma', 'Excel', 'Swift', 'Kotlin', 'Git', 'Linux']

def clean(value):
    value = re.sub(r'<[^>]*>', ' ', unescape(value or ''))
    return ' '.join(unescape(value).split())

def skills(text):
    return [s for s in SKILLS if re.search(r'(?<!\w)' + re.escape(s) + r'(?!\w)', text, re.I)]

def iso(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')
    return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')

def collect():
    jobs, status = [], []
    feeds = ([('Arbeitnow', f'https://www.arbeitnow.com/api/job-board-api?page={page}') for page in range(1, 5)]
             + [('Remotive', 'https://remotive.com/api/remote-jobs?limit=1000')])
    for name, url in feeds:
        try:
            response = requests.get(url, timeout=45, headers={'User-Agent': 'NextRole academic prototype/1.0'})
            response.raise_for_status()
            payload = response.json()
            rows = payload['data'] if name == 'Arbeitnow' else payload['jobs']
            count = 0
            seen = set()
            for row in rows:
                description = clean(row.get('description', ''))[:6000]
                title = clean(row['title'])
                job_url = row['url']
                if not job_url.startswith('https://') or job_url in seen:
                    continue
                seen.add(job_url)
                job_type = row.get('job_type', '')
                if job_type not in ['full_time', 'part_time', 'contract', 'internship']:
                    job_type = ''
                jobs.append(dict(id=hashlib.sha256((name + job_url).encode()).hexdigest()[:16], title=title,
                    company=clean(row['company_name']), location=clean(row.get('location', row.get('candidate_required_location', ''))),
                    country='', source=name, url=job_url, description=description,
                    work_mode='remote' if row.get('remote') or name == 'Remotive' else '',
                    job_type=job_type, posted_at=iso(row.get('created_at', row.get('publication_date'))), skills=skills(description)))
                count += 1
            status.append(dict(source=name, url=url, status='ok', count=count, sha256=hashlib.sha256(response.content).hexdigest()))
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            status.append(dict(source=name, url=url, status='failed', error=type(exc).__name__))
    if not jobs:
        raise RuntimeError('No public feed succeeded; do not replace live data with fictional records.')
    return jobs, status

def demo():
    roles = [
        ('Flutter Developer', 'Build accessible mobile applications with Flutter, Dart and REST APIs.', ['Flutter', 'Dart']),
        ('Mobile Application Engineer', 'Create Android and iOS apps using Flutter and Dart.', ['Flutter', 'Dart']),
        ('Android Developer', 'Develop native Android applications using Kotlin and Java.', ['Kotlin', 'Java']),
        ('iOS Engineer', 'Deliver accessible native iOS applications using Swift.', ['Swift']),
        ('React Developer', 'Build responsive websites with React and TypeScript.', ['React', 'TypeScript']),
        ('Frontend Engineer', 'Build accessible browser interfaces with JavaScript and React.', ['JavaScript', 'React']),
        ('Backend Developer', 'Develop reliable APIs with Go, PostgreSQL and Docker.', ['Go', 'PostgreSQL', 'Docker']),
        ('Python Engineer', 'Build REST services and data pipelines using Python and SQL.', ['Python', 'SQL']),
        ('Data Analyst', 'Analyse business datasets using SQL, Excel and Python.', ['SQL', 'Excel', 'Python']),
        ('Business Intelligence Analyst', 'Design business dashboards and measure product metrics with SQL.', ['SQL', 'Excel']),
        ('Data Scientist', 'Train statistical machine learning models using Python.', ['Python', 'SQL']),
        ('Platform Engineer', 'Operate Kubernetes and AWS infrastructure with Docker and Linux.', ['Kubernetes', 'AWS', 'Docker']),
        ('DevOps Engineer', 'Automate deployment pipelines on AWS using Docker and Kubernetes.', ['AWS', 'Docker', 'Kubernetes']),
        ('UX Designer', 'Research user needs and design accessible prototypes in Figma.', ['Figma']),
        ('Product Designer', 'Design user journeys and interactive prototypes in Figma.', ['Figma']),
        ('Accountant', 'Prepare accounts and reconcile financial transactions in Excel.', ['Excel']),
        ('Civil Engineer', 'Design bridges and inspect building structures.', []),
        ('Registered Nurse', 'Provide patient care and clinical assessment.', []),
        ('مطور تطبيقات', 'تطوير تطبيقات الهواتف باستخدام Flutter و Dart', ['Flutter', 'Dart']),
        ('محلل بيانات', 'تحليل البيانات باستخدام Python و SQL', ['Python', 'SQL']),
        ('مهندس برمجيات', 'تطوير خدمات الويب باستخدام Go و PostgreSQL', ['Go', 'PostgreSQL']),
        ('مهندسون معماريون', 'تصميم المباني والمساحات الداخلية', []),
    ]
    jobs=[]
    for i,(title,description,skillset) in enumerate(roles):
        jobs.append(dict(id=f'demo-{i+1:03}',title=title,company=f'Example Studio {i%5+1}',
            location='Dubai' if i%2==0 else 'Remote',country='AE' if i%2==0 else '',source='Synthetic fixture',url='',
            description=description,work_mode='hybrid' if i%2==0 else 'remote',job_type='full_time',
            posted_at='2026-09-20T09:00:00Z',skills=skillset))
    return jobs, [dict(source='Synthetic fixture',status='generated',count=len(jobs))]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
    jobs,status=collect() if args.live else demo()
    corpus=dict(dataset='public-feed-snapshot' if args.live else 'synthetic-functional-fixtures',
        collected_at=datetime.now(timezone.utc).isoformat(),model='',revision='',dimension=0,jobs=jobs)
    path=ROOT/'data'/('live.json' if args.live else 'demo.json');path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(corpus,ensure_ascii=False,indent=2))
    evidence=ROOT/'evidence';evidence.mkdir(exist_ok=True)
    (evidence/('source_import.json' if args.live else 'fixture_manifest.json')).write_text(json.dumps(status,indent=2))
    print(json.dumps({'path':str(path),'jobs':len(jobs),'sources':status}))

if __name__=='__main__':main()
