FROM public.ecr.aws/lambda/python:3.12

# Copy dependency list
COPY requirements.txt /tmp/requirements.txt

# Install third-party deps
RUN pip install --no-cache-dir -r /tmp/requirements.txt --target /opt/python

# Copy your app/package into the image
COPY . ${LAMBDA_TASK_ROOT}

# If your package is a proper Python package in the repo root:
# (optional; often not needed if you import via package on PYTHONPATH)
RUN pip install --no-cache-dir ${LAMBDA_TASK_ROOT} --target /opt/python

# Set the Lambda handler (module.function)
CMD ["ag.lambda_handler.lambda_handler"]
