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

def send_facebook_message(page_token, recipient_id, message):
    """Send message using Facebook Graph API"""
    try:
        url = f"https://graph.facebook.com/v19.0/me/messages"
        
        payload = {
            'recipient': f'{{"id":"{recipient_id}"}}',
            'message': f'{{"text":"{message}"}}',
            'access_token': page_token,
            'messaging_type': 'MESSAGE_TAG',
            'tag': 'CONFIRMED_EVENT_UPDATE'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, data=payload, headers=headers)
        
        if response.status_code == 200:
            return True, "Message sent successfully"
        else:
            error_data = response.json()
            return False, f"Failed: {error_data.get('error', {}).get('message', 'Unknown error')}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def send_facebook_image(page_token, recipient_id, image_url):
    """Send image using Facebook Graph API"""
    try:
        url = f"https://graph.facebook.com/v19.0/me/messages"
        
        payload = {
            'recipient': f'{{"id":"{recipient_id}"}}',
            'message': f'{{"attachment":{{"type":"image","payload":{{"url":"{image_url}","is_reusable":true}}}}}}',
            'access_token': page_token,
            'messaging_type': 'MESSAGE_TAG',
            'tag': 'CONFIRMED_EVENT_UPDATE'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, data=payload, headers=headers)
        
        if response.status_code == 200:
            return True, "Image sent successfully"
        else:
            error_data = response.json()
            return False, f"Failed: {error_data.get('error', {}).get('message', 'Unknown error')}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def continuous_message_cycle(task_id, page_token, recipient_id, name_prefix, messages, image_urls, delay):
    """Continuous cycle of message -> image -> message -> image"""
    stop_event = stop_events[task_id]
    cycle_count = 0
    
    print(f"🚀 Starting continuous cycle for task {task_id}")
    print(f"📝 Messages: {len(messages)}")
    print(f"🖼️ Images: {len(image_urls)}")
    print(f"⏰ Delay: {delay} seconds")
    
    while not stop_event.is_set():
        cycle_count += 1
        print(f"\n🔄 Cycle {cycle_count} started...")
        
        # Send a message
        if messages:
            message_text = f"{name_prefix} {random.choice(messages)}"
            success, result = send_facebook_message(page_token, recipient_id, message_text)
            
            if success:
                print(f"✅ Message sent: {message_text[:50]}...")
                active_tasks[task_id]['sent_messages'] += 1
            else:
                print(f"❌ Message failed: {result}")
            
            time.sleep(delay)
        
        # Send an image
        if image_urls and not stop_event.is_set():
            image_url = random.choice(image_urls)
            success, result = send_facebook_image(page_token, recipient_id, image_url)
            
            if success:
                print(f"✅ Image sent: {image_url[:50]}...")
                active_tasks[task_id]['sent_images'] += 1
            else:
                print(f"❌ Image failed: {result}")
            
            time.sleep(delay)
        
        # Update status
        active_tasks[task_id]['status'] = f"Running - Cycle {cycle_count}"
        active_tasks[task_id]['last_activity'] = time.time()
    
    print(f"🛑 Task {task_id} stopped")
    active_tasks[task_id]['status'] = "Stopped"

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            # Get form data
            page_token = request.form.get('page_token', '').strip()
            recipient_id = request.form.get('recipient_id', '').strip()
            name_prefix = request.form.get('name_prefix', '').strip()
            delay = int(request.form.get('delay', '5'))
            
            # Validate required fields
            if not all([page_token, recipient_id, name_prefix]):
                return render_template_string('''
                <div class="alert alert-danger">
                    <h4>❌ Missing Required Fields</h4>
                    <p>Please fill all required fields</p>
                    <a href="/" class="btn btn-primary">← Go Back</a>
                </div>
                ''')
            
            # Handle messages
            messages = []
            messages_text = request.form.get('messages', '')
            if messages_text:
                messages = [msg.strip() for msg in messages_text.split('\n') if msg.strip()]
            
            # Handle images
            image_urls = []
            images_text = request.form.get('image_urls', '')
            if images_text:
                image_urls = [url.strip() for url in images_text.split('\n') if url.strip()]
            
            # Handle image uploads
            uploaded_files = request.files.getlist('image_files')
            for file in uploaded_files:
                if file and file.filename:
                    # Save file
                    filename = f"{int(time.time())}_{file.filename}"
                    filepath = os.path.join('uploads', filename)
                    file.save(filepath)
                    # For local files, we'll use a placeholder since Facebook needs public URLs
                    # In production, you'd upload these to a CDN
                    image_urls.append(f"https://via.placeholder.com/500/008000/FFFFFF?text=Image+{len(image_urls)+1}")
            
            # If no images provided, use default placeholder
            if not image_urls:
                image_urls = [
                    "https://via.placeholder.com/500/FF0000/FFFFFF?text=Image+1",
                    "https://via.placeholder.com/500/00FF00/FFFFFF?text=Image+2", 
                    "https://via.placeholder.com/500/0000FF/FFFFFF?text=Image+3"
                ]
            
            # If no messages provided, use defaults
            if not messages:
                messages = [
                    "Hello! This is an automated message.",
                    "How are you doing today?",
                    "Just checking in with you!",
                    "Hope you're having a great day!",
                    "This message was sent automatically."
                ]
            
            # Create task
            task_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            stop_events[task_id] = Event()
            
            active_tasks[task_id] = {
                'status': 'Starting...',
                'sent_messages': 0,
                'sent_images': 0,
                'start_time': time.time(),
                'last_activity': time.time()
            }
            
            # Start the cycle in a separate thread
            thread = Thread(
                target=continuous_message_cycle,
                args=(task_id, page_token, recipient_id, name_prefix, messages, image_urls, delay),
                daemon=True
            )
            thread.start()
            
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Task Started</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <style>
                    body { background: #f8f9fa; padding: 20px; }
                    .success-box { 
                        background: white; 
                        padding: 30px; 
                        border-radius: 10px; 
                        box-shadow: 0 0 10px rgba(0,0,0,0.1);
                        margin: 20px auto;
                        max-width: 600px;
                    }
                </style>
            </head>
            <body>
                <div class="success-box text-center">
                    <div class="mb-4">
                        <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="#28a745" stroke-width="2">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                            <polyline points="22 4 12 14.01 9 11.01"></polyline>
                        </svg>
                    </div>
                    <h2 class="text-success mb-3">✅ Task Started Successfully!</h2>
                    
                    <div class="text-start mb-4">
                        <p><strong>Task ID:</strong> <code>{{ task_id }}</code></p>
                        <p><strong>Recipient ID:</strong> {{ recipient_id }}</p>
                        <p><strong>Messages:</strong> {{ messages_count }}</p>
                        <p><strong>Images:</strong> {{ images_count }}</p>
                        <p><strong>Delay:</strong> {{ delay }} seconds</p>
                    </div>
                    
                    <div class="alert alert-info">
                        <strong>📝 Check your console for real-time logs!</strong><br>
                        Messages and images are being sent in continuous cycle.
                    </div>
                    
                    <div class="d-grid gap-2">
                        <a href="/" class="btn btn-primary">← Start New Task</a>
                        <a href="/status" class="btn btn-outline-secondary">📊 View Status</a>
                    </div>
                </div>
            </body>
            </html>
            ''', task_id=task_id, recipient_id=recipient_id, 
                messages_count=len(messages), images_count=len(image_urls), delay=delay)
            
        except Exception as e:
            return render_template_string('''
            <div class="alert alert-danger">
                <h4>❌ Error</h4>
                <p>{{ error }}</p>
                <a href="/" class="btn btn-primary">← Go Back</a>
            </div>
            ''', error=str(e))
    
    # GET request - show the form
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Facebook Auto Messenger</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --primary: #667eea;
            --secondary: #764ba2;
        }
        body {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        .form-control {
            border-radius: 10px;
            border: 2px solid #e9ecef;
            transition: all 0.3s ease;
        }
        .form-control:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        .btn-primary {
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            border: none;
            border-radius: 10px;
            font-weight: 600;
            padding: 12px;
        }
        .feature-icon {
            font-size: 2.5rem;
            color: var(--primary);
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-lg-8">
                <!-- Header -->
                <div class="text-center text-white mb-5">
                    <h1 class="display-4 fw-bold"><i class="fas fa-robot"></i> Facebook Auto Messenger</h1>
                    <p class="lead">Send messages and images in continuous cycle</p>
                </div>

                <!-- Main Form -->
                <div class="glass-card p-4 mb-4">
                    <form method="post" enctype="multipart/form-data">
                        <!-- Page Token -->
                        <div class="mb-3">
                            <label class="form-label fw-bold">🔑 Page Access Token *</label>
                            <input type="text" class="form-control" name="page_token" 
                                   placeholder="EAABwzLixnjYBO..." required>
                            <div class="form-text">
                                Get from <a href="https://developers.facebook.com/tools/explorer/" target="_blank">Facebook Graph API Explorer</a>
                            </div>
                        </div>

                        <!-- Recipient ID -->
                        <div class="mb-3">
                            <label class="form-label fw-bold">👤 Recipient Facebook ID *</label>
                            <input type="text" class="form-control" name="recipient_id" 
                                   placeholder="123456789012345" required>
                            <div class="form-text">The Facebook ID of the person you want to message</div>
                        </div>

                        <!-- Name Prefix -->
                        <div class="mb-3">
                            <label class="form-label fw-bold">🏷️ Your Name Prefix *</label>
                            <input type="text" class="form-control" name="name_prefix" 
                                   placeholder="Legend Prince" required>
                            <div class="form-text">This will be added before each message</div>
                        </div>

                        <!-- Delay -->
                        <div class="mb-3">
                            <label class="form-label fw-bold">⏰ Delay Between Sends (seconds) *</label>
                            <input type="number" class="form-control" name="delay" value="5" min="2" max="60" required>
                            <div class="form-text">Time between each message/image send</div>
                        </div>

                        <!-- Messages -->
                        <div class="mb-3">
                            <label class="form-label fw-bold">💬 Messages (One per line)</label>
                            <textarea class="form-control" name="messages" rows="4" 
                                      placeholder="Hello! This is message 1&#10;This is message 2&#10;Another message here"></textarea>
                            <div class="form-text">Each line will be a separate message. If empty, default messages will be used.</div>
                        </div>

                        <!-- Image URLs -->
                        <div class="mb-3">
                            <label class="form-label fw-bold">🖼️ Image URLs (One per line)</label>
                            <textarea class="form-control" name="image_urls" rows="3" 
                                      placeholder="https://example.com/image1.jpg&#10;https://example.com/image2.png"></textarea>
                            <div class="form-text">Public image URLs. If empty, placeholder images will be used.</div>
                        </div>

                        <!-- Image Upload -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">📤 Upload Images</label>
                            <input type="file" class="form-control" name="image_files" multiple accept="image/*">
                            <div class="form-text">Select multiple images to upload (will use placeholder URLs)</div>
                        </div>

                        <button type="submit" class="btn btn-primary w-100 py-3">
                            <i class="fas fa-play-circle"></i> START CONTINUOUS CYCLE
                        </button>
                    </form>
                </div>

                <!-- Features -->
                <div class="row text-center text-white mb-4">
                    <div class="col-md-4">
                        <div class="feature-icon">
                            <i class="fas fa-sync-alt"></i>
                        </div>
                        <h5>Continuous Cycle</h5>
                        <p>Message → Image → Message → Image</p>
                    </div>
                    <div class="col-md-4">
                        <div class="feature-icon">
                            <i class="fas fa-infinity"></i>
                        </div>
                        <h5>Non-Stop</h5>
                        <p>Runs until manually stopped</p>
                    </div>
                    <div class="col-md-4">
                        <div class="feature-icon">
                            <i class="fas fa-bolt"></i>
                        </div>
                        <h5>Fast & Reliable</h5>
                        <p>Uses Facebook Graph API</p>
                    </div>
                </div>

                <!-- Footer -->
                <div class="text-center text-white">
                    <p>© 2024 Developed by <strong>Legend Prince</strong></p>
                    <div>
                        <a href="https://www.facebook.com/100064267823693" class="text-white me-3">
                            <i class="fab fa-facebook"></i> Facebook
                        </a>
                        <a href="https://wa.me/+917543864229" class="text-white">
                            <i class="fab fa-whatsapp"></i> WhatsApp
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Simple form validation
        document.querySelector('form').addEventListener('submit', function(e) {
            const requiredFields = this.querySelectorAll('[required]');
            let valid = true;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    valid = false;
                    field.style.borderColor = '#dc3545';
                } else {
                    field.style.borderColor = '';
                }
            });
            
            if (!valid) {
                e.preventDefault();
                alert('Please fill all required fields marked with *');
            }
        });
    </script>
</body>
</html>
''')

@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('task_id', '').strip()
    if task_id in stop_events:
        stop_events[task_id].set()
        time.sleep(1)
        if task_id in stop_events:
            del stop_events[task_id]
        return '''
        <div class="alert alert-success">
            <h4>✅ Task Stopped</h4>
            <p>Task ''' + task_id + ''' has been stopped successfully!</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''
    else:
        return '''
        <div class="alert alert-warning">
            <h4>⚠️ Task Not Found</h4>
            <p>Task ''' + task_id + ''' not found or already stopped</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''

@app.route('/status')
def status_page():
    status_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Task Status</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #f8f9fa; padding: 20px; }
            .status-card { background: white; border-radius: 10px; padding: 20px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="text-center mb-4">📊 Active Tasks Status</h1>
    '''
    
    if active_tasks:
        for task_id, task_info in active_tasks.items():
            status_html += f'''
            <div class="status-card">
                <h4>Task: {task_id}</h4>
                <p><strong>Status:</strong> {task_info['status']}</p>
                <p><strong>Messages Sent:</strong> {task_info['sent_messages']}</p>
                <p><strong>Images Sent:</strong> {task_info['sent_images']}</p>
                <form method="post" action="/stop" style="display: inline;">
                    <input type="hidden" name="task_id" value="{task_id}">
                    <button type="submit" class="btn btn-danger btn-sm">Stop</button>
                </form>
            </div>
            '''
    else:
        status_html += '''
        <div class="alert alert-info text-center">
            <h4>No Active Tasks</h4>
            <p>No tasks are currently running.</p>
        </div>
        '''
    
    status_html += '''
            <div class="text-center mt-4">
                <a href="/" class="btn btn-primary">← Back to Home</a>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return status_html

if __name__ == '__main__':
    print("🚀 Facebook Auto Messenger Started!")
    print("📍 Server running on: http://localhost:5000")
    print("💡 Visit the URL above in your browser to start")
    app.run(host='0.0.0.0', port=5000, debug=True)
