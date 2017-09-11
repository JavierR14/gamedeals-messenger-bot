from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import json
import os
import praw
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)
reddit = praw.Reddit(client_id='LMO9ciPUcNHmVQ', client_secret='bh-ypNImIGyoogFJFOKStuVI1ck', user_agent='web:com.gamedealsnotifierapp:v0.1.0 (by /u/yardz360)')

# Page Access Token from FB
PAT = 'EAAGojsu8t7UBAIX7BaQkj5rWvyNvXWoRP8coZBWUN81VxQaOyl7HTIiV4ZBYQQav5fXFwlE8LSH56vRcqZAvGTcKerVVf010hqlotVzUpGh38Jt4eTwte5zIvza6pwKeIwa1Ut2AOYnloLirLPLoZCDvA2bNElrpd24X5oF9qQZDZD'

#Temporary. TODO: Figure out how to auto-send notifications without requiring user message first
quick_reply_list = [
    {
        "content_type": "text",
        "title": "Game Deals",
        "payload": "gamedeals"
    },
    {
        "content_type": "text",
        "title": "PS4 Deals",
        "payload": "PS4Deals"
    },
    {
        "content_type": "text",
        "title": "Xbox Deals",
        "payload": "GreatXboxDeals"
    },
    {
        "content_type": "text",
        "title": "Steam Deals",
        "payload": "steamdeals"
    }
]

@app.route('/', methods=['GET'])
def handle_verification():
    print("Handling Verification.")
    if request.args.get('hub.verify_token', '') == 'my_voice_is_my_password_verify_me':
        print("Verification successful.")
        return request.args.get('hub.challenge', '')
    else:
        print("Verification failed.")
        return "Error, wrong validation token"

@app.route('/', methods=['POST'])
def handle_messages():
    print("Handling Messages.")
    payload = request.get_data()
    print(payload)
    for sender, message in messaging_events(payload):
        print("Incoming from %s, %s" % (sender, message))
        send_message(PAT, sender, message)
    return "OK"

def messaging_events(payload):
    """Generate tuples of (sender_id, message_text) from the
    provided payload.
    """
    data = json.loads(payload)
    messaging_events = data["entry"][0]["messaging"]
    for event in messaging_events:
        if "message" in event and "text" in event["message"]:
            yield event["sender"]["id"], event["message"]["text"].encode('unicode_escape')
        else:
            yield event["sender"]["id"], "I can't echo this message."

def send_message(token, recipient, text):
    #Send message back to sender who is now the recipient
    if "game" in text.lower():
        subreddit_name = "GameDeals"
    elif "ps4" in text.lower():
        subreddit_name = "PS4Deals"
    elif "xbox" in text.lower():
        subreddit_name = "GreatXboxDeals"
    else:
        subreddit_name = "steamdeals"

    user = get_or_create(db.session, Users, name=recipient)

    for submission in reddit.subreddit(subreddit_name).new(limit=25):
        query_result = Posts.query.filter(Posts.name == submission.id).first()
        if query_result is None:
            # Post has never been created before
            newPost = Posts(submission.id, submission.title, submission.url)
            user.posts.append(newPost)
            db.session.commit()
            if submission.title is not None:
                payload = submission.title
            else:
                payload = submission.title + '\n' + submission.url
            break
        elif user not in query_result.users:
            # Post exists but has not been sent to this user yet
            user.posts.append(query_result)
            db.session.commit()
            if submission.title is not None:
                payload = submission.title
            else:
                payload = submission.title + '\n' + submission.url
            break
        else:
            continue


    r = requests.post("https://graph.facebook.com/v2.6/me/messages",
        params={"access_token": token},
        data=json.dumps({
            "recipient": {"id": recipient},
            "message": {
                "text": payload,
                "quick_replies": quick_reply_list
            }
        }),
        headers={'Content-type': 'application/json'})

    if r.status_code != requests.codes.ok:
        print(r.text)

def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance

relationship_table=db.Table('relationship_table',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), nullable=False),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id'), nullable=False),
    db.PrimaryKeyConstraint('user_id', 'post_id'))

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    posts = db.relationship('Posts', secondary=relationship_table, backref='users')

    def __init__(self, name=None):
        self.name = name

class Posts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    title = db.Column(db.String, nullable=True)
    url = db.Column(db.String, nullable=False)

    def __init__(self, name, title=None, url):
        self.name = name
        self.title = title
        self.url = url

if __name__ == '__main__':
    app.run()
