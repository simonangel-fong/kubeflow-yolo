# Kubeflow: Monitoring

[Back](../README.md)

- [Kubeflow: Monitoring](#kubeflow-monitoring)
  - [](#)

---

##

```sh
# grafana UI
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80

# get password
aws secretsmanager get-secret-value --region ca-central-1 --secret-id kubeflow-yolo-dev/grafana-admin --query SecretString --output text

```
