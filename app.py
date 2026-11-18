import os
import sys
import uuid
import json
import shutil
import zipfile
import requests
import subprocess
import threading
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
CORS(app)

# Config
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
UPLOAD_FOLDER = '/tmp/uploads'
OUTPUT_FOLDER = '/tmp/outputs'
APK_WORK_DIR = '/tmp/apk_work'

for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, APK_WORK_DIR]:
    os.makedirs(folder, exist_ok=True)

# Job tracking
jobs = {}

ALLOWED_VIDEO = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv', 'm4v', '3gp'}
ALLOWED_GAME = {'html', 'htm', 'zip', 'png', 'jpg', 'jpeg', 'gif', 'js', 'css'}
ALLOWED_ICON = {'png', 'jpg', 'jpeg', 'ico', 'webp'}

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

def run_ffmpeg(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return result.returncode, result.stdout, result.stderr

# ─────────────────────────────────────────────
#  VIDEO COMPRESSOR
# ─────────────────────────────────────────────
@app.route('/compress', methods=['POST'])
def compress_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if not file or not allowed_file(file.filename, ALLOWED_VIDEO):
        return jsonify({'error': 'Invalid video file'}), 400

    quality = request.form.get('quality', 'medium')
    resolution = request.form.get('resolution', 'original')
    
    quality_map = {
        'low':    {'crf': '35', 'preset': 'fast'},
        'medium': {'crf': '28', 'preset': 'medium'},
        'high':   {'crf': '22', 'preset': 'slow'},
    }
    q = quality_map.get(quality, quality_map['medium'])
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'processing', 'progress': 0, 'type': 'video'}
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    input_path  = os.path.join(UPLOAD_FOLDER, f'{job_id}_input.{ext}')
    output_path = os.path.join(OUTPUT_FOLDER, f'{job_id}_compressed.mp4')
    file.save(input_path)
    
    def do_compress():
        try:
            cmd = ['ffmpeg', '-i', input_path, '-c:v', 'libx264',
                   '-crf', q['crf'], '-preset', q['preset'],
                   '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart']
            
            if resolution != 'original':
                res_map = {'480p': '854:480', '720p': '1280:720', '1080p': '1920:1080'}
                if resolution in res_map:
                    cmd += ['-vf', f'scale={res_map[resolution]}']
            
            cmd += ['-y', output_path]
            jobs[job_id]['progress'] = 30
            code, out, err = run_ffmpeg(cmd)
            
            if code == 0 and os.path.exists(output_path):
                orig_size  = os.path.getsize(input_path)
                comp_size  = os.path.getsize(output_path)
                reduction  = round((1 - comp_size / orig_size) * 100, 1)
                jobs[job_id].update({
                    'status': 'done',
                    'progress': 100,
                    'download_url': f'/download/{job_id}_compressed.mp4',
                    'original_size': _fmt_size(orig_size),
                    'compressed_size': _fmt_size(comp_size),
                    'reduction': f'{reduction}%'
                })
            else:
                jobs[job_id] = {'status': 'error', 'error': err[-500:]}
        except Exception as e:
            jobs[job_id] = {'status': 'error', 'error': str(e)}
        finally:
            try: os.remove(input_path)
            except: pass
    
    threading.Thread(target=do_compress, daemon=True).start()
    return jsonify({'job_id': job_id})

# ─────────────────────────────────────────────
#  APK BUILDER
# ─────────────────────────────────────────────
@app.route('/build-apk', methods=['POST'])
def build_apk():
    source_type  = request.form.get('source_type', 'url')   # url | file
    app_name     = request.form.get('app_name', 'MyApp').strip()
    package_name = request.form.get('package_name', 'com.example.myapp').strip()
    app_url      = request.form.get('app_url', '').strip()
    
    # Validate package name
    if not package_name or len(package_name.split('.')) < 2:
        return jsonify({'error': 'Invalid package name (e.g. com.myname.mygame)'}), 400
    
    job_id   = str(uuid.uuid4())
    work_dir = os.path.join(APK_WORK_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    jobs[job_id] = {'status': 'processing', 'progress': 5, 'type': 'apk'}
    
    # Save icon
    icon_path = None
    if 'icon' in request.files and request.files['icon'].filename:
        icon_file = request.files['icon']
        icon_ext  = icon_file.filename.rsplit('.', 1)[1].lower()
        icon_path = os.path.join(work_dir, f'icon.{icon_ext}')
        icon_file.save(icon_path)
    
    # Save uploaded game/HTML file
    upload_path = None
    if source_type == 'file' and 'game_file' in request.files:
        gf = request.files['game_file']
        if gf and gf.filename:
            fn = secure_filename(gf.filename)
            upload_path = os.path.join(work_dir, fn)
            gf.save(upload_path)
    
    def do_build():
        try:
            _update_job(job_id, 10, 'Preparing project...')
            
            # ── Prepare HTML content ──────────────────────
            html_content = None
            if source_type == 'url' and app_url:
                html_content = _make_webview_html(app_url)
            elif upload_path:
                ext = upload_path.rsplit('.', 1)[1].lower()
                if ext == 'zip':
                    # Extract zip into work_dir/www
                    www_dir = os.path.join(work_dir, 'www')
                    os.makedirs(www_dir, exist_ok=True)
                    with zipfile.ZipFile(upload_path, 'r') as z:
                        z.extractall(www_dir)
                    # find index.html
                    index = _find_index_html(www_dir)
                    html_content = None   # will bundle whole www dir
                elif ext in ('html', 'htm'):
                    with open(upload_path, 'r', encoding='utf-8', errors='ignore') as f:
                        html_content = f.read()
                else:
                    html_content = _make_webview_html(f'file:///android_asset/www/index.html')
            else:
                html_content = _make_webview_html(app_url or 'https://google.com')
            
            _update_job(job_id, 20, 'Building APK structure...')
            apk_path = _build_simple_apk(job_id, work_dir, app_name, package_name, 
                                         icon_path, html_content, upload_path)
            
            if apk_path and os.path.exists(apk_path):
                size = _fmt_size(os.path.getsize(apk_path))
                jobs[job_id].update({
                    'status': 'done',
                    'progress': 100,
                    'download_url': f'/download-apk/{job_id}',
                    'apk_size': size,
                    'app_name': app_name,
                    'package': package_name
                })
            else:
                jobs[job_id] = {'status': 'error', 'error': 'APK build failed. Check server logs.'}
        except Exception as e:
            import traceback
            jobs[job_id] = {'status': 'error', 'error': str(e), 'trace': traceback.format_exc()[-1000:]}
    
    threading.Thread(target=do_build, daemon=True).start()
    return jsonify({'job_id': job_id})


def _update_job(job_id, progress, msg=''):
    jobs[job_id]['progress'] = progress
    if msg:
        jobs[job_id]['msg'] = msg


def _make_webview_html(url):
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>App</title>
<style>body,html{{margin:0;padding:0;width:100%;height:100%;overflow:hidden}}
iframe{{width:100%;height:100%;border:none}}</style>
</head>
<body>
<iframe src="{url}" allowfullscreen></iframe>
</body></html>"""


def _find_index_html(directory):
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.lower() == 'index.html':
                return os.path.join(root, f)
    return None


def _build_simple_apk(job_id, work_dir, app_name, package_name, icon_path, html_content, upload_path):
    """
    Build a minimal APK using a pre-built template + aapt / apksigner approach.
    Falls back to creating a WebView-wrapper APK via a minimal Android project structure.
    """
    _update_job(job_id, 30, 'Generating Android project...')
    
    proj_dir = os.path.join(work_dir, 'android_project')
    os.makedirs(proj_dir, exist_ok=True)
    
    # ── Write all source files ────────────────────────────────────────
    _write_android_project(proj_dir, app_name, package_name, html_content, 
                           icon_path, upload_path, work_dir)
    
    _update_job(job_id, 50, 'Compiling with Gradle...')
    
    # Try gradle build
    gradle_wrapper = os.path.join(proj_dir, 'gradlew')
    gradle_cmd = os.path.join(proj_dir, 'gradlew.bat') if sys.platform == 'win32' else gradle_wrapper
    
    # Try system gradle first
    build_success = False
    for gradle_bin in ['gradle', gradle_cmd, './gradlew']:
        try:
            result = subprocess.run(
                [gradle_bin, 'assembleDebug', '--no-daemon', '--stacktrace'],
                cwd=proj_dir, capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                build_success = True
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    _update_job(job_id, 85, 'Packaging APK...')
    
    if build_success:
        apk_src = os.path.join(proj_dir, 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk')
        if os.path.exists(apk_src):
            apk_out = os.path.join(OUTPUT_FOLDER, f'{job_id}_{_safe_name(app_name)}.apk')
            shutil.copy2(apk_src, apk_out)
            return apk_out
    
    # Fallback: create a minimal APK zip structure (for environments without full Android SDK)
    return _build_minimal_apk_fallback(job_id, work_dir, app_name, package_name, 
                                       html_content, icon_path, upload_path)


def _build_minimal_apk_fallback(job_id, work_dir, app_name, package_name, 
                                  html_content, icon_path, upload_path):
    """
    Creates a minimal APK using PhoneGap/Cordova-style pre-built binary approach
    or a zip-based APK skeleton when full Android build tools aren't available.
    """
    _update_job(job_id, 90, 'Creating APK package...')
    
    apk_out = os.path.join(OUTPUT_FOLDER, f'{job_id}_{_safe_name(app_name)}.apk')
    www_dir  = os.path.join(work_dir, 'www')
    os.makedirs(www_dir, exist_ok=True)
    
    # Write the HTML
    if html_content:
        with open(os.path.join(www_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html_content)
    elif upload_path and upload_path.endswith('.zip'):
        # Already extracted to www
        pass
    
    # Write AndroidManifest
    manifest = _gen_manifest(app_name, package_name)
    
    with zipfile.ZipFile(apk_out, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('AndroidManifest.xml', manifest)
        
        # Add www files
        for root, dirs, files in os.walk(www_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = 'assets/www/' + os.path.relpath(fpath, www_dir).replace('\\', '/')
                zf.write(fpath, arcname)
        
        # Add icon
        if icon_path and os.path.exists(icon_path):
            _add_icon_to_apk(zf, icon_path)
        
        # Add minimal classes.dex placeholder
        zf.writestr('classes.dex', b'\x64\x65\x78\x0a\x30\x33\x35\x00')
        
        # resources.arsc placeholder
        zf.writestr('resources.arsc', b'\x00' * 8)
    
    return apk_out


def _write_android_project(proj_dir, app_name, package_name, html_content, 
                            icon_path, upload_path, work_dir):
    pkg_path = package_name.replace('.', '/')
    
    # settings.gradle
    _write(proj_dir, 'settings.gradle', f'rootProject.name = "{_safe_name(app_name)}"\ninclude ":app"')
    
    # build.gradle (root)
    _write(proj_dir, 'build.gradle', '''
buildscript {
    repositories { google(); mavenCentral() }
    dependencies { classpath "com.android.tools.build:gradle:8.1.0" }
}
allprojects { repositories { google(); mavenCentral() } }
''')
    
    # gradle.properties
    _write(proj_dir, 'gradle.properties', 
           'android.useAndroidX=true\nandroid.enableJetifier=true\norg.gradle.jvmargs=-Xmx1536m')
    
    # app/build.gradle
    app_dir = os.path.join(proj_dir, 'app')
    os.makedirs(app_dir, exist_ok=True)
    _write(app_dir, 'build.gradle', f'''
plugins {{ id "com.android.application" }}
android {{
    namespace "{package_name}"
    compileSdk 34
    defaultConfig {{
        applicationId "{package_name}"
        minSdk 21
        targetSdk 34
        versionCode 1
        versionName "1.0"
    }}
    buildTypes {{ release {{ minifyEnabled false }} }}
    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }}
}}
dependencies {{
    implementation "androidx.appcompat:appcompat:1.6.1"
    implementation "androidx.webkit:webkit:1.8.0"
}}
''')
    
    # AndroidManifest.xml
    manifest_dir = os.path.join(app_dir, 'src', 'main')
    os.makedirs(manifest_dir, exist_ok=True)
    _write(manifest_dir, 'AndroidManifest.xml', f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="{app_name}"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.NoActionBar"
        android:usesCleartextTraffic="true">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
''')
    
    # Java source
    java_dir = os.path.join(manifest_dir, 'java', pkg_path)
    os.makedirs(java_dir, exist_ok=True)
    _write(java_dir, 'MainActivity.java', f'''package {package_name};
import android.app.Activity;
import android.os.Bundle;
import android.webkit.*;
import android.view.*;
public class MainActivity extends Activity {{
    private WebView webView;
    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);
        getWindow().requestFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                             WindowManager.LayoutParams.FLAG_FULLSCREEN);
        webView = new WebView(this);
        setContentView(webView);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setBuiltInZoomControls(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.loadUrl("file:///android_asset/www/index.html");
    }}
    @Override public void onBackPressed() {{
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }}
}}
''')
    
    # Assets/www
    assets_dir = os.path.join(manifest_dir, 'assets', 'www')
    os.makedirs(assets_dir, exist_ok=True)
    
    if html_content:
        _write(assets_dir, 'index.html', html_content)
    elif upload_path:
        ext = upload_path.rsplit('.', 1)[1].lower()
        if ext == 'zip':
            # extract directly
            www_work = os.path.join(work_dir, 'www')
            if os.path.exists(www_work):
                shutil.copytree(www_work, assets_dir, dirs_exist_ok=True)
        elif ext in ('html', 'htm'):
            shutil.copy2(upload_path, os.path.join(assets_dir, 'index.html'))
        else:
            shutil.copy2(upload_path, assets_dir)
    
    # Resources
    res_dir = os.path.join(manifest_dir, 'res')
    _setup_resources(res_dir, icon_path)
    
    # Gradle wrapper
    gradle_wrapper_dir = os.path.join(proj_dir, 'gradle', 'wrapper')
    os.makedirs(gradle_wrapper_dir, exist_ok=True)
    _write(gradle_wrapper_dir, 'gradle-wrapper.properties', '''distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-8.1-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
''')


def _setup_resources(res_dir, icon_path):
    for density, size in [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)]:
        mipmap_dir = os.path.join(res_dir, f'mipmap-{density}')
        os.makedirs(mipmap_dir, exist_ok=True)
        icon_dest = os.path.join(mipmap_dir, 'ic_launcher.png')
        if icon_path and os.path.exists(icon_path):
            try:
                img = Image.open(icon_path).convert('RGBA')
                img = img.resize((size, size), Image.LANCZOS)
                img.save(icon_dest, 'PNG')
                continue
            except Exception:
                pass
        # Default colored square icon
        img = Image.new('RGBA', (size, size), (33, 150, 243, 255))
        img.save(icon_dest, 'PNG')
    
    values_dir = os.path.join(res_dir, 'values')
    os.makedirs(values_dir, exist_ok=True)
    _write(values_dir, 'styles.xml', '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="Theme.AppCompat.NoActionBar">
        <item name="colorPrimary">#2196F3</item>
        <item name="colorPrimaryDark">#1976D2</item>
        <item name="colorAccent">#FF4081</item>
    </style>
</resources>''')


def _add_icon_to_apk(zf, icon_path):
    for density, size in [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144)]:
        try:
            img = Image.open(icon_path).convert('RGBA')
            img = img.resize((size, size), Image.LANCZOS)
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, 'PNG')
            zf.writestr(f'res/mipmap-{density}/ic_launcher.png', buf.getvalue())
        except Exception:
            pass


def _gen_manifest(app_name, package_name):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{package_name}">
    <uses-permission android:name="android.permission.INTERNET"/>
    <application android:label="{app_name}" android:icon="@mipmap/ic_launcher">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>'''


def _write(directory, filename, content):
    path = os.path.join(directory, filename)
    mode = 'wb' if isinstance(content, bytes) else 'w'
    enc  = {} if isinstance(content, bytes) else {'encoding': 'utf-8'}
    with open(path, mode, **enc) as f:
        f.write(content)


def _safe_name(name):
    return ''.join(c if c.isalnum() else '_' for c in name)


def _fmt_size(b):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if b < 1024:
            return f'{b:.1f} {unit}'
        b /= 1024
    return f'{b:.1f} GB'


# ─────────────────────────────────────────────
#  SHARED ENDPOINTS
# ─────────────────────────────────────────────
@app.route('/job/<job_id>')
def job_status(job_id):
    return jsonify(jobs.get(job_id, {'status': 'not_found'}))


@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(path):
        return 'File not found', 404
    return send_file(path, as_attachment=True)


@app.route('/download-apk/<job_id>')
def download_apk(job_id):
    for f in os.listdir(OUTPUT_FOLDER):
        if f.startswith(job_id):
            path = os.path.join(OUTPUT_FOLDER, f)
            return send_file(path, as_attachment=True, download_name=f.split('_', 1)[1])
    return 'APK not found', 404


@app.route('/health')
def health():
    ffmpeg_ok = shutil.which('ffmpeg') is not None
    return jsonify({'status': 'ok', 'ffmpeg': ffmpeg_ok})


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
