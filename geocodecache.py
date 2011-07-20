import geocode
from flask import request
from flask import jsonify
from flask import Flask
from middleware import ReverseProxied

app = Flask(__name__)
app.wsgi_app = ReverseProxied(app.wsgi_app)

@app.route('/geocode', methods=['GET'])
def geocode_get():
  lat, lng = geocode.Geocode(request.args['q'])
  return jsonify(lat=lat, lng=lng)


if __name__ == "__main__":
  app.run(debug=True, port=5007)
