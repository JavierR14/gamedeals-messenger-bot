# -*- coding: utf-8 -*-
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import json
import os
import praw
import requests

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db = SQLAlchemy(app)
reddit = praw.Reddit(client_id=os.environ['REDDIT_CLIENT_ID'], client_secret=os.environ['REDDIT_CLIENT_SECRET'], user_agent='web:com.gamedealsnotifierapp:v0.1.0 (by /u/yardz360)')

# Page Access Token from FB
PAT = os.environ['PAGE_ACCESS_TOKEN']

introMessage = "Hi! All Gaming Deals here. I'll give you all of the gaming deals as they release depending on your preferences! 🙂 \n" + "\n" + "Press any of the Quick-Reply buttons below to instantly receive deals from the chosen category." + "\n" + "\n" + "Say 'SUBSCRIBE <category>' to *start* receiving deals automatically from that category." + "\n" + "\n" + "Say 'UNSUBSCRIBE <category>' to *stop* receiving deals automatically from that category." + "\n" + "\n" + "_Categories_" + "\n" + "*GameDeals*" + "\n" + "*PS4Deals*" + "\n" + "*XboxDeals*" + "\n" + "*SteamDeals*"

#Temporary. TODO: Figure out how to auto-send notifications without requiring user message first
quick_reply_list = [
    {
        "content_type": "text",
        "title": "Help",
        "payload": introMessage
    },
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
        send_message(sender, message)
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

def send_message(recipient, text):
    #Send message back to sender who is now the recipient
    text = text.decode('unicode_escape')

    requiresIntro = False

    if "game" in text.lower():
        subreddit_name = "GameDeals"
    elif "ps4" in text.lower():
        subreddit_name = "PS4Deals"
    elif "xbox" in text.lower():
        subreddit_name = "GreatXboxDeals"
    elif "steam" in text.lower():
        subreddit_name = "steamdeals"
    else:
        subreddit_name = ""

    if not Users.query.filter(Users.name == recipient).first() or not subreddit_name:
        requiresIntro = True
        post_message(introMessage, recipient)


    user = get_or_create(db.session, Users, name=recipient)

    if not requiresIntro:
        send_messages_for_subreddit(subreddit_name, user, text)


# Automatically notifies users of new deals based on their subscriptions.
def send_subscription_messages():
    subreddits = ["GameDeals", "GreatXboxDeals", "PS4Deals", "steamdeals"]
    subredditPosts = {}
    for s in subreddits:
        subredditPosts[s] = reddit.subreddit(s).new(limit=25)

    users = Users.query.all()
    for user in users:
        # TO DO, send messages for subreddits they are subscribed to.
        # Temp: Send notification for all subreddits
        for name in subredditPosts:
            send_messages_for_subreddit(name, user, name, subredditPosts[name])



def send_messages_for_subreddit(subreddit_name, user, text, subreddit_posts=None):
    newContent = False
    newSubmissions = subreddit_posts or reddit.subreddit(subreddit_name).new(limit=25)

    for submission in newSubmissions:
        query_result = Posts.query.filter(Posts.name == submission.id).first()
        if query_result is None:
            # Post has never been created before
            newPost = Posts(submission.id, submission.url, submission.title)
            user.posts.append(newPost)
            db.session.commit()

            newContent = True
            payload = submission.title + '\n' + submission.url

        elif user not in query_result.users:
            # Post exists but has not been sent to this user yet
            user.posts.append(query_result)
            db.session.commit()

            newContent = True
            payload = submission.title + '\n' + submission.url
        else:
            continue

        post_message(payload, user.name)

    if newContent:
        payload = "Those are all of the new deals for " + text + " at the moment."
        post_message(payload, user.name)
    elif not subreddit_posts:
        payload = "No new deals since last update for " + text + "."
        post_message(payload, user.name)

def post_message(payload, recipient):
    r = requests.post("https://graph.facebook.com/v2.6/me/messages",
        params={"access_token": PAT},
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

def get(session, model, **kwargs):
    return session.query(model).filter_by(**kwargs).first()

def create(session, model, **kwargs):
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

    def __init__(self, name, url, title=None):
        self.name = name
        self.title = title
        self.url = url

if __name__ == '__main__':
    app.run()
