import os
import tornado.ioloop
import tornado.web
import tornado.log
import queries
import json
import requests
import datetime
from jinja2 import Environment, PackageLoader, select_autoescape

owm_api_key=os.environ.get('OWM_API_KEY')

ENV = Environment(
    loader = PackageLoader('weather', 'templates'),
    autoescape=select_autoescape(['html', 'xml']))
    
class TemplateHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.session = queries.Session(
            'postgresql://postgres@localhost:5432/weatherapp')
    
    def render_template (self, tpl, context):
        template = ENV.get_template(tpl)
        self.write(template.render(**context))

class MainHandler(TemplateHandler):
    def setCache(self, weatherJSON):
        weatherJSON = weatherJSON.json()
        self.session.query('''INSERT INTO cacheweather VALUES (
                DEFAULT, %(cityname)s, %(iconurl)s, %(weatherdescription)s, 
                %(temp)s, %(windspeed)s, %(winddir)s, %(lastupdate)s, %(weatherid)s)
                ''', {
                    'cityname': weatherJSON['name'],
                    'iconurl':'https://openweathermap.org/img/w/'+ weatherJSON['weather'][0]['icon'] +'.png',
                    'weatherdescription':weatherJSON['weather'][0]['description'],
                    'temp': weatherJSON['main']['temp'],
                    'windspeed':weatherJSON['wind']['speed'],
                    'winddir':weatherJSON['wind']['deg'],
                    'lastupdate': datetime.datetime.utcnow(),
                    'weatherid': weatherJSON['weather'][0]['id']
        })

    def setContext(self, weatherJSON):
        weatherJSON = weatherJSON.json()
        context = {
            'city': weatherJSON['name'],
            'iconURL': 'https://openweathermap.org/img/w/'+ weatherJSON['weather'][0]['icon'] +'.png',
            # 'weatherid' : weatherJSON['weather'][0]['id'],
            'description': weatherJSON['weather'][0]['description'],
            'temp': weatherJSON['main']['temp'],
            'windspeed': weatherJSON['wind']['speed'],
            'winddir':weatherJSON['wind']['deg'],
            'weatherid' :weatherJSON['weather'][0]['id']
        }
        return context
    
    def getCache(self, db_id):
        db_entry = self.session.query('SELECT * FROM cacheweather WHERE id = %(id)s', {'id': str(db_id)})
        context = {
            'city': db_entry[0]['cityname'],
            'iconURL': db_entry[0]['iconurl'],
            'weatherdescription': db_entry[0]['weatherdescription'],
            'temp': db_entry[0]['temp'],
            'windspeed': db_entry[0]['windspeed'],
            'winddir':db_entry[0]['winddir'],
            'weatherid': db_entry[0]['weatherid']
        }
        return context
        
    
    def get(self):
        # posts = self.session.query('SELECT * FROM post')
        self.render_template('weatherhome.html', {})
        
    def post(self):
        location = self.get_body_argument('location', None)
        apisite = 'https://api.openweathermap.org/data/2.5/weather'
        payload = {'q': location, 'appid' : owm_api_key, 'units': 'imperial'}
        lastupdate = self.session.query('''
            SELECT lastupdate, id FROM cacheweather WHERE cityname=%(location)s ORDER BY lastupdate DESC LIMIT 1
            ''', {'location':location})
        if(lastupdate and (lastupdate[0]['lastupdate'] > datetime.datetime.utcnow() - datetime.timedelta(minutes=15))):
            context = self.getCache(lastupdate[0]['id'])
            self.render_template("weatherhome.html", {'context': context})
        else:
            owmJSONcall = requests.get(apisite, params = payload)
            self.setCache(owmJSONcall)
            context = self.setContext(owmJSONcall)
            self.render_template("weatherhome.html", {'context': context})
           
#This is the "tornado" code!
def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {'path': 'static'} ),
    ], autoreload=True)

if __name__ == "__main__":
    tornado.log.enable_pretty_logging()
    app = make_app()
    app.listen(int(os.environ.get('PORT', '8080')))
    tornado.ioloop.IOLoop.current().start()