
```sh
helm repo add jupyterhub https://jupyterhub.github.io/helm-chart/
helm repo add jupyterhub https://hub.jupyter.org/helm-chart/
helm search repo jupyterhub
helm repo update

helm upgrade -i jupyter-notebook jupyterhub/jupyterhub --version  4.4.1 
```