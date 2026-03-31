# Native validator: in-tree Python rules on deserialized scandata.
ARG BASE_IMAGE=localhost/apme-base:latest
FROM $BASE_IMAGE

ENV APME_NATIVE_VALIDATOR_LISTEN=0.0.0.0:50055
EXPOSE 50055

CMD ["apme-native-validator"]
