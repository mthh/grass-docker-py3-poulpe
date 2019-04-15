FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive

ARG GRASS_VERSION=7.7
ARG GRASS_SHORT_VERSION=77

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

# download grass gis source
WORKDIR /src
# this line should break docker cache if there are changes - weekly updated
ADD https://grass.osgeo.org/grass${GRASS_SHORT_VERSION}/source/snapshot/ChangeLog.gz /src/ChangeLog.gz
RUN wget https://grass.osgeo.org/grass${GRASS_SHORT_VERSION}/source/snapshot/grass-${GRASS_VERSION}.svn_src_snapshot_latest.tar.gz
RUN mkdir -p /src/grass_build && \
    tar xfz grass-$GRASS_VERSION.svn_src_snapshot_latest.tar.gz --strip=1 -C /src/grass_build && \
    rm -f grass-$GRASS_VERSION.svn_src_snapshot_latest.tar.gz
WORKDIR /src/grass_build
# this line should break docker cache if there are changes after snapshot
ADD https://svn.osgeo.org/grass/grass/ /src/TrunkRevision.html
RUN svn update

# Set environmental variables for GRASS GIS compilation, without debug symbols
ENV INTEL "-march=native -std=gnu99 -fexceptions -fstack-protector -m64"
ENV MYCFLAGS "-O2 -fno-fast-math -fno-common $INTEL"
ENV MYLDFLAGS "-s -Wl,--no-undefined"
# CXX stuff:
ENV LD_LIBRARY_PATH "/usr/local/lib"
ENV LDFLAGS "$MYLDFLAGS"
ENV CFLAGS "$MYCFLAGS"
ENV CXXFLAGS "$MYCXXFLAGS"

# Fixup python shebangs - TODO: will be resolved in future by grass-core
WORKDIR /src/grass_build
RUN find -name '*.py' | xargs sed -i 's,#!/usr/bin/env python,#!/usr/bin/env python3,'
RUN sed -i 's,python,python3,' include/Make/Platform.make.in

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
ENV INTEL ""
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

RUN grass --config svn_revision version

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
ENV GISBASE "/usr/local/grass77/"
ENV GRASSBIN "/usr/local/bin/grass"
ENV PYTHONPATH "${PYTHONPATH}:$GISBASE/etc/python/"
ENV LD_LIBRARY_PATH "$LD_LIBRARY_PATH:$GISBASE/lib"

WORKDIR /grassdb
VOLUME /grassdb

RUN grass --config revision version
WORKDIR /home
RUN mkdir /home/app && cd /home/app
COPY index.html /home/app/index.html
COPY grenoble_est_eudem_2154.zip /home/app/grenoble_est_eudem_2154.zip
COPY app.py /home/app/app.py
WORKDIR /home/app
RUN unzip grenoble_est_eudem_2154.zip
EXPOSE 5000
CMD python3 app.py
