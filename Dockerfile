FROM python:3.8.2-slim-buster

# Prevents python from buffering output.
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install dependencies
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    # django
    libpq-dev gcc && \
    apt-get clean

RUN pip install --upgrade pip
COPY ./requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

RUN mkdir /api
WORKDIR /api
COPY ./api /api

# RUN mkdir -p /vol/web/media
# RUN mkdir -p /vol/web/static
# We do this user thing for security purposes.
# If we didn't create this user, our app would be run by root, which is dangerous.
RUN addgroup --system user && adduser --system --no-create-home --group user
RUN chown -R user:user /api && chmod -R 755 /api
# RUN adduser -D user
# RUN chown -R user:user /vol/
# RUN chmod -R 755 /vol/web
USER user
