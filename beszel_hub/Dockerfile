FROM henrygd/beszel:latest

# henrygd/beszel je distroless (nema shell) => zadny RUN nejde.
# Misto symlinku jen prepiseme CMD, aby beszel psal PocketBase data do /data
# (perzistentni add-on volume HAOS) => prezije restart i update add-onu.
# ENTRYPOINT ["/beszel"] se dedi z base image.
CMD ["serve", "--http=0.0.0.0:8090", "--dir=/data"]
