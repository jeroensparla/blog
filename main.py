
from flask import Flask, render_template_string, request
import requests
from bs4 import BeautifulSoup
from wordcloud import WordCloud, STOPWORDS
import base64
from io import BytesIO
import re

app = Flask(__name__)

def fetch_blog_posts(n=10):
    base_url = 'https://www.academictransfer.com'
    blog_url = f'{base_url}/nl/blog/'
    response = requests.get(blog_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    posts = []
    links = [a['href'] for a in soup.select('a') if '/nl/blog/' in a.get('href', '')]
    seen = set()

    for link in links:
        if len(posts) >= n:
            break
        full_url = link if link.startswith('http') else base_url + link
        if full_url in seen:
            continue
        seen.add(full_url)
        try:
            article = requests.get(full_url)
            post_soup = BeautifulSoup(article.text, 'html.parser')
            content = post_soup.select_one('div.article__content, .blog__content, main')
            if content:
                text = content.get_text(strip=True)
                title = post_soup.title.string if post_soup.title else 'Untitled'
                posts.append({'title': title, 'link': full_url, 'content': text})
        except Exception as e:
            print("Error:", e)
    return posts

def generate_wordcloud(posts):
    text = ' '.join(p['content'] for p in posts if p['content'].strip())
    stopwords = set(STOPWORDS)
    wc = WordCloud(
        width=800,
        height=400,
        background_color='white',
        stopwords=stopwords,
        regexp=r'\b[a-zA-Z]{5,}\b'
    ).generate(text)
    img = BytesIO()
    wc.to_image().save(img, format='PNG')
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode(), list(wc.words_.keys())[:100]

def extract_tags(text):
    words = re.findall(r'\b[a-zA-Z]{5,}\b', text.lower())
    return sorted(set(w for w in words if w not in STOPWORDS))

topic_map = {
    'research': ['research', 'method', 'publication'],
    'career': ['career', 'vacancy', 'job', 'position'],
    'events': ['conference', 'presentation', 'network'],
    'phd': ['phd', 'supervisor', 'thesis', 'candidate']
}

def classify_topics(text):
    topics = []
    for topic, keywords in topic_map.items():
        if any(word in text.lower() for word in keywords):
            topics.append(topic)
    return topics

# Preprocess data
posts_cache = fetch_blog_posts()
for post in posts_cache:
    post['tags'] = extract_tags(post['content'])[:5]
    post['topics'] = classify_topics(post['content'])

encoded_wc, top_words = generate_wordcloud(posts_cache)

@app.route('/')
def index():
    keyword = request.args.get('word', '').lower()
    tag = request.args.get('tag', '').lower()
    topic = request.args.get('topic', '').lower()

    filtered = posts_cache
    if keyword:
        filtered = [p for p in filtered if keyword in p['title'].lower() or keyword in p['content'].lower()]
    if tag:
        filtered = [p for p in filtered if tag in p['tags']]
    if topic:
        filtered = [p for p in filtered if topic in p['topics']]

    html = """
    <html><head><title>Blog Explorer</title></head><body>
    <h1>Interactive Blog WordCloud</h1>
    <img src='data:image/png;base64,{{ img }}' width='800'/><br><br>
    <h3>Click a word to filter posts:</h3>
    {% for word in words %}<a href='/?word={{word}}'>{{word}}</a> · {% endfor %}
    <hr><h3>Topics:</h3>
    {% for t in ['research','career','events','phd'] %}<a href='/?topic={{t}}'>[{{t}}]</a> {% endfor %}
    <hr><h2>Matching Blog Posts ({{ filtered|length }})</h2>
    <ul>
    {% for post in filtered %}
    <li><a href='{{ post.link }}' target='_blank'>{{ post.title }}</a><br>
    Tags: {% for tag in post.tags %}<a href='/?tag={{tag}}'>#{{tag}}</a> {% endfor %}<br>
    Topics: {{ post.topics|join(', ') }}
    </li>
    {% endfor %}
    </ul>
    </body></html>
    """
    return render_template_string(html, img=encoded_wc, words=top_words, filtered=filtered)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
