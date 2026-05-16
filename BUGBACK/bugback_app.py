from flask import Flask, request, Response, jsonify, send_file, render_template
import json
import queue
import threading
from bugback_agent import BugBackAgent
from bugback_agent.memory import PersistentMemory

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/investigate', methods=['POST'])
def investigate():
    data = request.get_json()
    complaint = data['complaint']
    base_url = data.get('base_url', 'http://127.0.0.1:5001')

    def generate():
        step_q = queue.Queue()

        def on_step(step):
            step_q.put(('step', {
                'step': step.step, 'title': step.title,
                'detail': step.detail, 'tool': step.tool, 'evidence': step.evidence,
            }))

        def run():
            try:
                agent = BugBackAgent(base_url=base_url, memory_path='data/memory.json', on_step=on_step)
                result = agent.investigate(complaint)
                step_q.put(('done', result.to_dict()))
            except Exception as e:
                step_q.put(('error', str(e)))

        threading.Thread(target=run, daemon=True).start()

        while True:
            try:
                kind, payload = step_q.get(timeout=120)
                yield f"data: {json.dumps({'type': kind, 'payload': payload})}\n\n"
                if kind in ('done', 'error'):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'error', 'payload': 'Request timed out'})}\n\n"
                break

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/screenshot')
def screenshot():
    try:
        return send_file(request.args.get('path', ''), mimetype='image/png')
    except Exception:
        return '', 404


@app.route('/clear-memory', methods=['POST'])
def clear_memory():
    PersistentMemory('data/memory.json').clear()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8501, debug=False, threaded=True)
