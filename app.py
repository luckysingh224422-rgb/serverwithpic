from flask import Flask, request, render_template_string, send_file
import requests
import time
import random
import string
import os
import json
import io
from threading import Thread, Event
from PIL import Image

app = Flask(__name__)

# Create directories
if not os.path.exists('uploads'):
    os.makedirs('uploads')
if not os.path.exists('static'):
    os.makedirs('static')

# Global variables
stop_events = {}
active_tasks = {}

def upload_image_to_imgbb(image_path, api_key='your_imgbb_api_key_here'):
    """Upload image to ImgBB and get URL"""
    try:
        url = "https://api.imgbb.com/1/upload"
        
        with open(image_path, 'rb') as file:
            files = {'image': file}
            data = {'key': api_key}
            
            response = requests.post(url, files=files, data=data)
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                return True, result['data']['url']
            else:
                return False, f"Upload failed: {result.get('error', {}).get('message', 'Unknown error')}"
                
    except Exception as e:
        return False, f"Upload error: {str(e)}"

def create_placeholder_image(text, filename):
    """Create a placeholder image with text"""
    try:
        img = Image.new('RGB', (500, 500), color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
        
        # Save image
        img_path = os.path.join('static', filename)
        img.save(img_path)
        
        # For local development, serve from static folder
        return f"http://localhost:5000/static/{filename}"
    except Exception as e:
        return f"https://via.placeholder.com/500/008000/FFFFFF?text={text}"

def send_facebook_message(page_token, recipient_id, message):
    """Send message using Facebook Graph API"""
    try:
        url = f"https://graph.facebook.com/v19.0/me/messages"
        
        payload = {
            'recipient': json.dumps({'id': recipient_id}),
            'message': json.dumps({'text': message}),
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
            'recipient': json.dumps({'id': recipient_id}),
            'message': json.dumps({
                'attachment': {
                    'type': 'image',
                    'payload': {
                        'url': image_url,
                        'is_reusable': True
                    }
                }
            }),
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

def process_uploaded_images(uploaded_files):
    """Process uploaded images and return URLs"""
    image_urls = []
    
    for file in uploaded_files:
        if file and file.filename:
            try:
                # Save original file
                filename = f"{int(time.time())}_{random.randint(1000,9999)}_{file.filename}"
                filepath = os.path.join('uploads', filename)
                file.save(filepath)
                
                print(f"📁 Image saved: {filename}")
                
                # Create placeholder image with the filename
                placeholder_url = create_placeholder_image(f"Image{len(image_urls)+1}", filename)
                image_urls.append(placeholder_url)
                
                print(f"🖼️ Placeholder created: {placeholder_url}")
                
            except Exception as e:
                print(f"❌ Error processing image: {str(e)}")
                # Add fallback URL
                image_urls.append(f"https://via.placeholder.com/500/FF0000/FFFFFF?text=Error+{len(image_urls)+1}")
    
    return image_urls

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
        print(f"\n🎯 Cycle {cycle_count}")
        
        # Send a message
        if messages:
            message_text = f"{name_prefix} {random.choice(messages)}"
            success, result = send_facebook_message(page_token, recipient_id, message_text)
            
            if success:
                print(f"✅ Message {active_tasks[task_id]['sent_messages'] + 1}: {message_text[:50]}...")
                active_tasks[task_id]['sent_messages'] += 1
            else:
                print(f"❌ Message failed: {result}")
            
            time.sleep(delay)
        
        # Send an image
        if image_urls and not stop_event.is_set():
            image_url = random.choice(image_urls)
            success, result = send_facebook_image(page_token, recipient_id, image_url)
            
            if success:
                print(f"✅ Image {active_tasks[task_id]['sent_images'] + 1}: {image_url[:50]}...")
                active_tasks[task_id]['sent_images'] += 1
            else:
                print(f"❌ Image failed: {result}")
            
            time.sleep(delay)
        
        # Update status
        active_tasks[task_id]['status'] = f"Running - Cycle {cycle_count}"
        active_tasks[task_id]['last_activity'] = time.time()
        active_tasks[task_id]['total_cycles'] = cycle_count
    
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
                return '''
                <div class="alert alert-danger">
                    <h4>❌ Missing Required Fields</h4>
                    <p>Please fill all required fields</p>
                    <a href="/" class="btn btn-primary">← Go Back</a>
                </div>
                '''
            
            # Handle messages
            messages = []
            messages_text = request.form.get('messages', '')
            if messages_text:
                messages = [msg.strip() for msg in messages_text.split('\n') if msg.strip()]
            
            # Handle image uploads
            uploaded_files = request.files.getlist('image_files')
            image_urls = process_uploaded_images(uploaded_files)
            
            # If no images uploaded, use default placeholders
            if not image_urls:
                image_urls = [
                    create_placeholder_image("Auto1", "default1.jpg"),
                    create_placeholder_image("Auto2", "default2.jpg"),
                    create_placeholder_image("Auto3", "default3.jpg")
                ]
                print("🔄 Using default placeholder images")
            
            # If no messages provided, use defaults
            if not messages:
                messages = [
                    "Hello! This is an automated message.",
                    "How are you doing today?",
                    "Just checking in with you!",
                    "Hope you're having a great day!",
                    "This message was sent automatically.",
                    "Enjoy your day!",
                    "Sending positive vibes!",
                    "Have a wonderful time!",
                    "Stay blessed!",
                    "Take care!"
                ]
            
            # Create task
            task_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            stop_events[task_id] = Event()
            
            active_tasks[task_id] = {
                'status': 'Starting...',
                'sent_messages': 0,
                'sent_images': 0,
                'start_time': time.time(),
                'last_activity': time.time(),
                'total_cycles': 0
            }
            
            # Start the cycle in a separate thread
            thread = Thread(
                target=continuous_message_cycle,
                args=(task_id, page_token, recipient_id, name_prefix, messages, image_urls, delay),
                daemon=True
            )
            thread.start()
            
            success_html = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Task Started</title>
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
                <style>
                    body {{ 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        padding: 20px;
                    }}
                    .success-box {{ 
                        background: rgba(255, 255, 255, 0.95);
                        padding: 40px; 
                        border-radius: 15px; 
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                        margin: 20px auto;
                        max-width: 700px;
                        text-align: center;
                    }}
                    .stats-box {{
                        background: #f8f9fa;
                        border-radius: 10px;
                        padding: 20px;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-box">
                        <div class="mb-4">
                            <i class="fas fa-check-circle text-success" style="font-size: 4rem;"></i>
                        </div>
                        <h2 class="text-success mb-3">✅ Task Started Successfully!</h2>
                        
                        <div class="stats-box text-start">
                            <div class="row">
                                <div class="col-md-6">
                                    <p><strong>Task ID:</strong> <code>{task_id}</code></p>
                                    <p><strong>Recipient ID:</strong> {recipient_id}</p>
                                    <p><strong>Your Name:</strong> {name_prefix}</p>
                                </div>
                                <div class="col-md-6">
                                    <p><strong>Messages:</strong> {len(messages)}</p>
                                    <p><strong>Images:</strong> {len(image_urls)}</p>
                                    <p><strong>Delay:</strong> {delay} seconds</p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="alert alert-info">
                            <i class="fas fa-terminal"></i> 
                            <strong>Check your console for real-time logs!</strong><br>
                            <small>Messages and images are being sent in continuous cycle: Message → Image → Message → Image</small>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <a href="/" class="btn btn-primary w-100 mb-2">
                                    <i class="fas fa-home"></i> New Task
                                </a>
                            </div>
                            <div class="col-md-6">
                                <a href="/status" class="btn btn-success w-100 mb-2">
                                    <i class="fas fa-chart-bar"></i> View Status
                                </a>
                            </div>
                        </div>
                        
                        <div class="mt-3">
                            <form method="post" action="/stop" class="d-inline">
                                <input type="hidden" name="task_id" value="{task_id}">
                                <button type="submit" class="btn btn-danger">
                                    <i class="fas fa-stop"></i> Stop This Task
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            '''
            
            return success_html
            
        except Exception as e:
            return f'''
            <div class="alert alert-danger">
                <h4>❌ Error</h4>
                <p>{str(e)}</p>
                <a href="/" class="btn btn-primary">← Go Back</a>
            </div>
            '''
    
    # GET request - show the form
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Facebook Auto Messenger - Upload Method</title>
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
            padding: 20px;
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
        .preview-image {
            width: 100px;
            height: 100px;
            object-fit: cover;
            border-radius: 10px;
            margin: 5px;
            border: 2px solid var(--primary);
        }
        .upload-area {
            border: 2px dashed #667eea;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            background: rgba(102, 126, 234, 0.1);
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .upload-area:hover {
            background: rgba(102, 126, 234, 0.2);
        }
    </style>
</head>
<body>
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-lg-10">
                <!-- Header -->
                <div class="text-center text-white mb-5">
                    <h1 class="display-4 fw-bold"><i class="fas fa-upload"></i> Facebook Auto Messenger</h1>
                    <p class="lead">Upload Images & Send Messages in Continuous Cycle</p>
                </div>

                <!-- Main Form -->
                <div class="glass-card p-4 mb-4">
                    <form method="post" enctype="multipart/form-data" id="mainForm">
                        <!-- Page Token -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">🔑 Page Access Token *</label>
                            <input type="text" class="form-control" name="page_token" 
                                   placeholder="EAABwzLixnjYBO..." required>
                            <div class="form-text">
                                <i class="fas fa-info-circle"></i> Get from 
                                <a href="https://developers.facebook.com/tools/explorer/" target="_blank">Facebook Graph API Explorer</a>
                            </div>
                        </div>

                        <!-- Recipient ID -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">👤 Recipient Facebook ID *</label>
                            <input type="text" class="form-control" name="recipient_id" 
                                   placeholder="123456789012345" required>
                            <div class="form-text">The Facebook ID of the person you want to message</div>
                        </div>

                        <!-- Name Prefix -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">🏷️ Your Name Prefix *</label>
                            <input type="text" class="form-control" name="name_prefix" 
                                   placeholder="Legend Prince" required>
                            <div class="form-text">This will be added before each message</div>
                        </div>

                        <!-- Delay -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">⏰ Delay Between Sends (seconds) *</label>
                            <input type="number" class="form-control" name="delay" value="5" min="2" max="60" required>
                            <div class="form-text">Time between each message/image send (recommended: 5+ seconds)</div>
                        </div>

                        <!-- Messages -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">💬 Messages (One per line) *</label>
                            <textarea class="form-control" name="messages" rows="5" 
                                      placeholder="Hello! This is message 1&#10;This is message 2&#10;Another message here&#10;You can add multiple messages" required></textarea>
                            <div class="form-text">Each line will be a separate message in the cycle</div>
                        </div>

                        <!-- Image Upload -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">🖼️ Upload Images *</label>
                            <div class="upload-area" onclick="document.getElementById('image_files').click()">
                                <i class="fas fa-cloud-upload-alt fa-3x text-primary mb-3"></i>
                                <h5>Click to Upload Images</h5>
                                <p class="text-muted">Select multiple images (JPG, PNG, GIF)</p>
                                <small class="text-muted">Supported formats: JPG, PNG, GIF</small>
                            </div>
                            <input type="file" class="form-control d-none" id="image_files" name="image_files" multiple accept="image/*" required>
                            <div class="form-text">Select multiple images to use in the cycle (minimum 1 image required)</div>
                            <div id="image_preview" class="mt-3"></div>
                        </div>

                        <button type="submit" class="btn btn-primary w-100 py-3">
                            <i class="fas fa-play-circle"></i> START CONTINUOUS CYCLE
                        </button>
                    </form>
                </div>

                <!-- How It Works -->
                <div class="glass-card p-4 mb-4">
                    <h4 class="fw-bold mb-3"><i class="fas fa-info-circle"></i> How It Works:</h4>
                    <div class="row">
                        <div class="col-md-6">
                            <h6>📁 Image Upload Process:</h6>
                            <ol>
                                <li>Select multiple images using the upload area</li>
                                <li>Images are saved to server</li>
                                <li>Placeholder URLs are generated</li>
                                <li>Images are ready for sending</li>
                            </ol>
                        </div>
                        <div class="col-md-6">
                            <h6>🔄 Sending Cycle:</h6>
                            <ol>
                                <li>Message 1 → Random Image → Message 2 → Random Image</li>
                                <li>Continuous loop until stopped</li>
                                <li>Random selection from your messages & images</li>
                                <li>Real-time console logs</li>
                            </ol>
                        </div>
                    </div>
                </div>

                <!-- Features -->
                <div class="row text-center text-white mb-4">
                    <div class="col-md-3">
                        <div class="feature-icon">
                            <i class="fas fa-upload"></i>
                        </div>
                        <h6>Image Upload</h6>
                        <p>Direct upload support</p>
                    </div>
                    <div class="col-md-3">
                        <div class="feature-icon">
                            <i class="fas fa-sync-alt"></i>
                        </div>
                        <h6>Auto Cycle</h6>
                        <p>Message → Image → Repeat</p>
                    </div>
                    <div class="col-md-3">
                        <div class="feature-icon">
                            <i class="fas fa-infinity"></i>
                        </div>
                        <h6>Non-Stop</h6>
                        <p>Runs continuously</p>
                    </div>
                    <div class="col-md-3">
                        <div class="feature-icon">
                            <i class="fas fa-chart-line"></i>
                        </div>
                        <h6>Live Tracking</h6>
                        <p>Real-time status</p>
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
        // Image preview functionality
        document.getElementById('image_files').addEventListener('change', function(e) {
            const preview = document.getElementById('image_preview');
            preview.innerHTML = '';
            
            const files = e.target.files;
            const uploadArea = document.querySelector('.upload-area');
            
            if (files.length > 0) {
                uploadArea.innerHTML = `
                    <i class="fas fa-check-circle text-success fa-3x mb-3"></i>
                    <h5 class="text-success">${files.length} Images Selected</h5>
                    <p class="text-muted">Click to change selection</p>
                `;
                
                Array.from(files).forEach((file, index) => {
                    if (file.type.startsWith('image/')) {
                        const reader = new FileReader();
                        reader.onload = function(e) {
                            const img = document.createElement('img');
                            img.src = e.target.result;
                            img.className = 'preview-image';
                            img.title = file.name;
                            preview.appendChild(img);
                        }
                        reader.readAsDataURL(file);
                    }
                });
            } else {
                uploadArea.innerHTML = `
                    <i class="fas fa-cloud-upload-alt fa-3x text-primary mb-3"></i>
                    <h5>Click to Upload Images</h5>
                    <p class="text-muted">Select multiple images (JPG, PNG, GIF)</p>
                `;
            }
        });

        // Form validation
        document.getElementById('mainForm').addEventListener('submit', function(e) {
            const files = document.getElementById('image_files').files;
            if (files.length === 0) {
                e.preventDefault();
                alert('❌ Please upload at least one image!');
                return false;
            }
            
            // Show loading state
            const btn = this.querySelector('button[type="submit"]');
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> PROCESSING IMAGES...';
            btn.disabled = true;
        });
    </script>
</body>
</html>
''')

@app.route('/static/<filename>')
def serve_static(filename):
    """Serve static files (placeholder images)"""
    try:
        return send_file(f'static/{filename}')
    except:
        return "File not found", 404

@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('task_id', '').strip()
    if task_id in stop_events:
        stop_events[task_id].set()
        time.sleep(1)
        if task_id in stop_events:
            del stop_events[task_id]
        return '''
        <div class="alert alert-success text-center">
            <h4>✅ Task Stopped</h4>
            <p>Task ''' + task_id + ''' has been stopped successfully!</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''
    else:
        return '''
        <div class="alert alert-warning text-center">
            <h4>⚠️ Task Not Found</h4>
            <p>Task ''' + task_id + ''' not found or already stopped</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''

@app.route('/status')
def status_page():
    """Status page to monitor active tasks"""
    status_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Task Status</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .status-card { 
                background: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                padding: 25px;
                margin: 15px 0;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="text-center text-white mb-4">
                <h1><i class="fas fa-chart-bar"></i> Active Tasks Status</h1>
            </div>
    '''
    
    if active_tasks:
        for task_id, task_info in active_tasks.items():
            runtime = int(time.time() - task_info['start_time'])
            status_html += f'''
            <div class="status-card">
                <div class="row">
                    <div class="col-md-8">
                        <h4>Task: <code>{task_id}</code></h4>
                        <p><strong>Status:</strong> <span class="badge bg-success">{task_info['status']}</span></p>
                        <p><strong>Runtime:</strong> {runtime} seconds</p>
                        <p><strong>Cycles Completed:</strong> {task_info['total_cycles']}</p>
                    </div>
                    <div class="col-md-4">
                        <div class="text-end">
                            <p><strong>Messages Sent:</strong> <span class="badge bg-primary">{task_info['sent_messages']}</span></p>
                            <p><strong>Images Sent:</strong> <span class="badge bg-info">{task_info['sent_images']}</span></p>
                            <form method="post" action="/stop">
                                <input type="hidden" name="task_id" value="{task_id}">
                                <button type="submit" class="btn btn-danger btn-sm">
                                    <i class="fas fa-stop"></i> Stop Task
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            '''
    else:
        status_html += '''
        <div class="status-card text-center">
            <h4>No Active Tasks</h4>
            <p class="text-muted">No tasks are currently running.</p>
            <a href="/" class="btn btn-primary">Start New Task</a>
        </div>
        '''
    
    status_html += '''
            <div class="text-center mt-4">
                <a href="/" class="btn btn-light">
                    <i class="fas fa-arrow-left"></i> Back to Home
                </a>
            </div>
        </div>
    </body>
    </html>
    '''
    
    return status_html

if __name__ == '__main__':
    print("🚀 Facebook Auto Messenger with Upload Method Started!")
    print("📍 Server running on: http://localhost:5000")
    print("📁 Upload folder created: ./uploads/")
    print("🖼️ Static folder created: ./static/")
    print("💡 Visit the URL above in your browser to start")
    app.run(host='0.0.0.0', port=5000, debug=True)
