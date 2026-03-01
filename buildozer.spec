[app]

# (str) Title of your application
title = Метеостанция

# (str) Package name
package.name = meteorstation

# (str) Package domain (needed for android/ios packaging)
package.domain = org.yourname

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let everything)
source.include_exts = py,png,jpg,kv,atlas,txt,json

# (str) Application versioning (method 1)
version = 0.1

# (list) Application requirements
requirements = python3,kivy,pyjnius,android

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions for Android 12+
android.permissions = BLUETOOTH_SCAN, BLUETOOTH_CONNECT, BLUETOOTH_ADMIN, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION

# (list) extra permissions for older Android versions
android.extra_permissions = android.permission.BLUETOOTH, android.permission.BLUETOOTH_ADMIN, android.permission.BLUETOOTH_SCAN, android.permission.BLUETOOTH_CONNECT

# (int) Target Android API
android.api = 33

# (int) Minimum API your APK will support
android.minapi = 21

# (int) Android SDK version to use
android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25b

# (bool) If True, then automatically accept SDK license
android.accept_sdk_license = True

# (str) Android arch to build for
android.arch = arm64-v8a

# (str) Specific build_tools version to use
android.build_tools_version = 34.0.0

# (str) Python-for-android branch
p4a.branch = develop

[buildozer]
# (int) Log level (0-2)
log_level = 2
