from flask import Flask, send_from_directory

app = Flask(__name__)

@app.route('/')
@app.route('/index.html')
def home():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run()
