from apscheduler.schedulers.blocking import BlockingScheduler
from rq import Queue
from worker import conn
from app import send_subscription_messages

import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

sched = BlockingScheduler()

q = Queue(connection=conn)

def send_posts():
    q.enqueue(send_subscription_messages)

sched.add_job(send_posts) #enqueue right away once
sched.add_job(send_posts, 'interval', minutes=1)
sched.start()
