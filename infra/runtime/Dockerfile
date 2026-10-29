ARG PHP_VERSION=8.4
FROM php:${PHP_VERSION}-apache
# Use HTTPS and keep archived Bullseye security packages available for old PHP.
# Only the archived source skips Release-date expiry; signatures remain checked.
RUN set -eux; for file in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do \
      if [ -f "$file" ]; then sed -i \
        -e 's|http://deb.debian.org/debian-security|https://security.debian.org/debian-security|g' \
        -e 's|http://security.debian.org/debian-security|https://security.debian.org/debian-security|g' \
        -e 's|http://deb.debian.org/debian|https://deb.debian.org/debian|g' "$file"; fi; \
    done; \
    . /etc/os-release; \
    if [ "${VERSION_CODENAME:-}" = bullseye ]; then \
      for file in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do \
        if [ -f "$file" ]; then sed -i '/bullseye-security/d' "$file"; fi; \
      done; \
      printf 'deb [check-valid-until=no] https://archive.debian.org/debian-security bullseye-security main\n' > /etc/apt/sources.list.d/vmm-security.list; \
    fi
RUN apt-get update && apt-get install -y --no-install-recommends libicu-dev libzip-dev libpng-dev libjpeg62-turbo-dev libfreetype6-dev libonig-dev libxml2-dev libgmp-dev libxslt1-dev unzip curl ca-certificates default-mysql-client \
 && docker-php-ext-configure gd --with-freetype --with-jpeg \
 && docker-php-ext-install -j2 mysqli pdo_mysql intl zip gd mbstring exif bcmath soap sockets gmp xsl \
 && if ! php -m | grep -qi opcache; then docker-php-ext-install opcache; fi \
 && a2enmod rewrite headers \
 && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --retry 2 https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar -o /usr/local/bin/wp && chmod +x /usr/local/bin/wp
RUN printf '<Directory /var/www/html>\nAllowOverride All\nRequire all granted\n</Directory>\n' > /etc/apache2/conf-enabled/vmm.conf \
 && printf 'memory_limit=256M\nupload_max_filesize=512M\npost_max_size=520M\nmax_execution_time=300\nauto_prepend_file=/vmm-tools/prepend.php\n' > /usr/local/etc/php/conf.d/vmm.ini
WORKDIR /var/www/html
RUN printf '<FilesMatch "(^\\.|\\.vmm-original$|^configuration\\.php$|^wp-config\\.php$)">\nRequire all denied\n</FilesMatch>\n' > /etc/apache2/conf-enabled/vmm-private.conf
