FROM python:3.9-slim-buster

COPY /protect_with_atakama /protect_with_atakama
COPY ./requirements.txt /

RUN pip install --upgrade setuptools pip
RUN pip install --requirement requirements.txt

EXPOSE 54321
CMD waitress-serve --port=54321 protect_with_atakama.app:app
