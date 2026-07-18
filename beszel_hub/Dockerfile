FROM henrygd/beszel:latest

# Beszel uklada data do /beszel_data. Presmerujeme je do /data (perzistentni
# add-on volume HAOS) pres symlink, aby prezila restart i update add-onu.
RUN rm -rf /beszel_data && ln -s /data/beszel_data /beszel_data
