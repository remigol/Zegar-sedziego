#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/toolchains
cat > /workspace/toolchains/android-env.sh <<'ANDROID_ENV_EOF'
export JAVA_HOME=/workspace/toolchains/jdk17
export ANDROID_HOME=/workspace/toolchains/android-sdk
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export ANDROID_USER_HOME=/workspace/cache/android
export GRADLE_USER_HOME=/workspace/cache/gradle
export PATH="$JAVA_HOME/bin:/workspace/toolchains/gradle-8.9/bin:$ANDROID_HOME/cmdline-tools/19.0/bin:$ANDROID_HOME/platform-tools:$PATH"
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:+$JAVA_TOOL_OPTIONS }-Djavax.net.ssl.trustStore=/workspace/toolchains/java-cacerts"
ANDROID_ENV_EOF
cat > /workspace/toolchains/setup-android.sh <<'ANDROID_SETUP_EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /workspace/toolchains
mkdir -p /workspace/cache/gradle /workspace/cache/android
fetch() {
  local url="$1" file="$2" checksum="$3" algorithm="$4"
  if ! python3 - "$file" "$checksum" "$algorithm" <<'PY'
import hashlib,pathlib,sys
p=pathlib.Path(sys.argv[1])
sys.exit(0 if p.exists() and hashlib.new(sys.argv[3],p.read_bytes()).hexdigest()==sys.argv[2] else 1)
PY
  then curl -fLsS --retry 2 "$url" -o "$file"; fi
  python3 - "$file" "$checksum" "$algorithm" <<'PY'
import hashlib,pathlib,sys
assert hashlib.new(sys.argv[3],pathlib.Path(sys.argv[1]).read_bytes()).hexdigest()==sys.argv[2], 'Artifact checksum mismatch'
PY
}
fetch 'https://services.gradle.org/distributions/gradle-8.9-bin.zip' gradle-8.9-bin.zip d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab sha256
if [ ! -f gradle-8.9/bin/gradle ]; then python3 -m zipfile -e gradle-8.9-bin.zip .; fi
chmod +x gradle-8.9/bin/gradle
fetch 'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.16%2B8/OpenJDK17U-jdk_x64_linux_hotspot_17.0.16_8.tar.gz' jdk17.tar.gz 166774efcf0f722f2ee18eba0039de2d685b350ee14d7b69e6f83437dafd2af1 sha256
mkdir -p jdk17
if [ ! -f jdk17/bin/java ]; then tar -xzf jdk17.tar.gz --strip-components=1 -C jdk17; fi
fetch 'https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u462-b08/OpenJDK8U-jdk_x64_linux_hotspot_8u462b08.tar.gz' jdk8.tar.gz 5d64ae542b59a962b3caadadd346f4b1c3010879a28bb02d928326993de16e79 sha256
mkdir -p jdk8
if [ ! -f jdk8/bin/java ]; then tar -xzf jdk8.tar.gz --strip-components=1 -C jdk8; fi
fetch 'https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip' android-cli.zip 5fdcc763663eefb86a5b8879697aa6088b041e70 sha1
if [ ! -f android-sdk/cmdline-tools/19.0/bin/sdkmanager ]; then
  mkdir -p android-sdk/cmdline-tools/19.0
  python3 -m zipfile -e android-cli.zip android-sdk/cmdline-tools/19.0
  mv android-sdk/cmdline-tools/19.0/cmdline-tools/* android-sdk/cmdline-tools/19.0/
  rmdir android-sdk/cmdline-tools/19.0/cmdline-tools
fi
chmod +x android-sdk/cmdline-tools/19.0/bin/*
cp jdk17/lib/security/cacerts java-cacerts
for cert in /usr/local/share/ca-certificates/*.crt; do
  [ -f "$cert" ] || continue
  jdk17/bin/keytool -importcert -noprompt -trustcacerts -keystore java-cacerts -storepass changeit -alias "environment-$(basename "$cert" .crt)" -file "$cert"
done
python3 - <<'PY'
import os,pathlib,urllib.parse,shlex
u=urllib.parse.urlparse(os.environ.get('HTTPS_PROXY',os.environ.get('https_proxy','')))
props=['systemProp.javax.net.ssl.trustStore=/workspace/toolchains/java-cacerts', 'org.gradle.java.installations.paths=/workspace/toolchains/jdk8,/workspace/toolchains/jdk17', 'systemProp.http.nonProxyHosts=localhost|127.*']
flags=[]
if u.hostname:
 for scheme in ('http','https'):
  props += [f'systemProp.{scheme}.proxyHost={u.hostname}',f'systemProp.{scheme}.proxyPort={u.port or 80}']
 flags=['--proxy=http',f'--proxy_host={u.hostname}',f'--proxy_port={u.port or 80}']
pathlib.Path('/workspace/cache/gradle/gradle.properties').write_text('\n'.join(props)+'\n')
pathlib.Path('/workspace/toolchains/sdk-proxy.sh').write_text('SDK_PROXY_FLAGS=('+ ' '.join(map(shlex.quote,flags))+')\n')
PY
source /workspace/toolchains/android-env.sh
source /workspace/toolchains/sdk-proxy.sh
set +o pipefail
yes | sdkmanager --sdk_root="$ANDROID_HOME" "${SDK_PROXY_FLAGS[@]}" --licenses
license_status=${PIPESTATUS[1]}
set -o pipefail
[ "$license_status" -eq 0 ]
sdkmanager --sdk_root="$ANDROID_HOME" "${SDK_PROXY_FLAGS[@]}" 'platforms;android-35' 'build-tools;34.0.0' 'platform-tools'
mkdir -p /home/agent/.android
java -version
gradle --version
adb version
test -f "$ANDROID_HOME/platforms/android-35/android.jar"
test -x "$ANDROID_HOME/build-tools/34.0.0/aapt2"
ANDROID_SETUP_EOF
bash /workspace/toolchains/setup-android.sh
