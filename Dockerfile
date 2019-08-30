FROM python:3

WORKDIR /stumpy
COPY . .

RUN ./setup.sh
RUN pip install -U pytest
RUN pip install dask distributed --upgrade

CMD ["bash"]
