# How to use:
# docker run -it --rm -v <your path to your data folder>:/data <your image>

FROM python:3.7
RUN mkdir /data
RUN python -m pip install bruker==0.3.3

CMD echo '--------------------'; \
    echo 'To use the bids converter:'; \
    echo 'first run bids_helper'; \
    echo 'brkraw bids_helper <input dir> <output filename> -j'; \
    echo 'second, run converter'; \
    echo 'brkraw bids_convert <input dir> <BIDS datasheet.xlsx> -j <JSON syntax template.json> -o <output dir>';\
    echo '--------------------'; \
    bash

