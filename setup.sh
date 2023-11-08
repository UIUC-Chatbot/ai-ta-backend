# Install Google Chrome
apt-get update && apt-get install -y \
  wget \
  unzip \
  libglib2.0-0 \
  libnss3 \
  libgconf-2-4 \
  libfontconfig1 \
  && wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
  && dpkg -i google-chrome-stable_current_amd64.deb; apt-get -fy install

# Install ChromeDriver
wget https://chromedriver.storage.googleapis.com/2.41/chromedriver_linux64.zip \
  && unzip chromedriver_linux64.zip \
  && mv chromedriver /usr/bin/chromedriver \
  && chown root:root /usr/bin/chromedriver \
  && chmod +x /usr/bin/chromedriver