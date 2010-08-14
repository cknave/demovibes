import uwsgi

from bottle import route, default_app

event = None

def event_receiver(obj, id):
    global event
    event = obj
    uwsgi.green_unpause_all()

uwsgi.message_manager_marshal = event_receiver

@route('/demovibes/ajax/monitor/:id/')
def handler(id):
    id = int(id)
    yield ""

    if not event or event[1] <= id:
        uwsgi.green_pause(60)
    levent = [x[1] for x in event[0] if x[0] >= id]
    levent = set(levent)
    yield "\n".join(levent)
    yield "\n!%s" % event[1]
        
application = default_app()
