FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive

ARG GRASS_VERSION=7.9
ARG GRASS_SHORT_VERSION=79

SHELL ["/bin/bash", "-c"]

WORKDIR /tmp

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends --no-install-suggests \
    build-essential \
    bison \
    bzip2 \
    cmake \
    curl \
    flex \
    g++ \
    gcc \
    gdal-bin \
    git \
    language-pack-en-base \
    libbz2-dev \
    libcairo2 \
    libcairo2-dev \
    libcurl4-gnutls-dev \
    libfftw3-bin \
    libfftw3-dev \
    libfreetype6-dev \
    libgdal-dev \
    libgeos-dev \
    libgsl0-dev \
    libjpeg-dev \
    libjsoncpp-dev \
    libopenblas-base \
    libopenblas-dev \
    libnetcdf-dev \
    libncurses5-dev \
    libopenjp2-7 \
    libopenjp2-7-dev \
    libpnglite-dev \
    libpq-dev \
    libproj-dev \
    libpython3-all-dev \
    libsqlite3-dev \
    libtiff-dev \
    libzstd-dev \
    make \
    mesa-common-dev \
    moreutils \
    ncurses-bin \
    netcdf-bin \
    python3 \
    python3-dateutil \
    python3-dev \
    python3-magic \
    python3-numpy \
    python3-pil \
    python3-pip \
    python3-ply \
    python3-setuptools \
    python3-venv \
    software-properties-common \
    sqlite3 \
    subversion \
    unzip \
    vim \
    wget \
    zip \
    zlib1g-dev

RUN echo LANG="en_US.UTF-8" > /etc/default/locale

# download grass gis source from git
ARG SOURCE_GIT_URL=https://github.com
ARG SOURCE_GIT_REMOTE=OSGeo
ARG SOURCE_GIT_REPO=grass
ARG SOURCE_GIT_BRANCH=master

WORKDIR /src
ADD https://api.github.com/repos/$SOURCE_GIT_REMOTE/$SOURCE_GIT_REPO/git/refs/heads/$SOURCE_GIT_BRANCH version.json
RUN git clone -b ${SOURCE_GIT_BRANCH} --single-branch ${SOURCE_GIT_URL}/${SOURCE_GIT_REMOTE}/${SOURCE_GIT_REPO}.git grass_build
WORKDIR /src/grass_build

# Set environmental variables for GRASS GIS compilation, without debug symbols
ENV MYCFLAGS "-O2 -std=gnu99 -m64"
ENV MYLDFLAGS "-s"
ENV LD_LIBRARY_PATH "/usr/local/lib"
ENV LDFLAGS "$MYLDFLAGS"
ENV CFLAGS "$MYCFLAGS"
ENV CXXFLAGS "$MYCXXFLAGS"

# Configure compile and install GRASS GIS
ENV GRASS_PYTHON=/usr/bin/python3
ENV NUMTHREADS=4
RUN make distclean || echo "nothing to clean"
RUN /src/grass_build/configure \
  --with-cxx \
  --enable-largefile \
  --with-proj --with-proj-share=/usr/share/proj \
  --with-gdal=/usr/bin/gdal-config \
  --with-geos \
  --with-sqlite \
  --with-cairo --with-cairo-ldflags=-lfontconfig \
  --with-freetype --with-freetype-includes="/usr/include/freetype2/" \
  --with-fftw \
  --with-netcdf \
  --with-zstd \
  --with-bzlib \
  --without-mysql \
  --without-odbc \
  --without-openmp \
  --without-ffmpeg \
  --without-opengl \
    && make -j $NUMTHREADS \
    && make install && ldconfig

# Unset environmental variables to avoid later compilation issues
ENV MYCFLAGS ""
ENV MYLDFLAGS ""
ENV MYCXXFLAGS ""
ENV LD_LIBRARY_PATH ""
ENV LDFLAGS ""
ENV CFLAGS ""
ENV CXXFLAGS ""

# set SHELL var to avoid /bin/sh fallback in interactive GRASS GIS sessions
ENV SHELL /bin/bash
ENV LC_ALL "en_US.UTF-8"
ENV GRASS_SKIP_MAPSET_OWNER_CHECK 1

# Create generic GRASS GIS binary name regardless of version number
RUN ln -sf `find /usr/local/bin -name "grass??" | sort | tail -n 1` /usr/local/bin/grass

# Reduce the image size
RUN apt-get autoremove -y
RUN apt-get clean -y

WORKDIR /scripts
ADD requirements.txt /scripts
RUN pip3 install -r /scripts/requirements.txt

# TODO: is there a better workaround to install addons?
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1
RUN update-alternatives --remove python /usr/bin/python3


# add GRASS GIS envs for python usage
ENV GISBASE "/usr/local/grass79/"
ENV GRASSBIN "/usr/local/bin/grass"
ENV PYTHONPATH "${PYTHONPATH}:$GISBASE/etc/python/"
ENV LD_LIBRARY_PATH "$LD_LIBRARY_PATH:$GISBASE/lib"

WORKDIR /grassdb
VOLUME /grassdb

WORKDIR /home
RUN mkdir /home/app && cd /home/app
COPY index.html /home/app/index.html
COPY *.zip /home/app/
COPY app.py /home/app/app.py
WORKDIR /home/app
RUN unzip *.zip
EXPOSE 5000
CMD python3 app.py
