#!/usr/bin/env bash
# Task 3 demo: deploy v1, rolling update to v2 with zero downtime, roll back to v1,
# then delete a pod to show Kubernetes self-healing (a mini Chaos Monkey).
# Assumes catalog-service:v1 and :v2 are already loaded into the kind cluster.
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n========== %s ==========\n' "$1"; }
run()  { printf '$ %s\n' "$*"; "$@"; }
# Wait until pods from the old version have fully shut down
settle() { while kubectl get pods -l app=catalog-service --no-headers | grep -q Terminating; do sleep 1; done; }
version() { run kubectl exec deploy/loadgen -- wget -qO- http://catalog-service/; echo; }

step "1. Deploy v1"
run kubectl apply -f deployment.yaml -f service.yaml -f loadgen.yaml
run kubectl rollout status deployment/catalog-service --timeout=120s
kubectl rollout status deployment/loadgen --timeout=120s >/dev/null
run kubectl get pods -l app=catalog-service -o wide
version

step "2. Rolling update v1 -> v2"
# Watcher pod hits the service every 0.25s during the update to prove there is no downtime
kubectl delete pod rollout-watch --ignore-not-found >/dev/null
kubectl run rollout-watch --image=busybox:1.37 --restart=Never -- sh -c \
  'for i in $(seq 1 160); do wget -qO- -T 2 http://catalog-service/ 2>/dev/null || echo FAIL; echo; sleep 0.25; done' >/dev/null
kubectl wait --for=condition=Ready pod/rollout-watch --timeout=60s >/dev/null
run kubectl set image deployment/catalog-service catalog-service=catalog-service:v2
run kubectl annotate deployment/catalog-service kubernetes.io/change-cause="v2: new release" --overwrite
run kubectl rollout status deployment/catalog-service --timeout=120s
run kubectl get rs -l app=catalog-service
run kubectl get pods -l app=catalog-service
settle
version
kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/rollout-watch --timeout=90s >/dev/null
logs=$(kubectl logs rollout-watch)
v1=$(echo "$logs" | grep -c '"v1"' || true)
v2=$(echo "$logs" | grep -c '"v2"' || true)
failed=$(echo "$logs" | grep -c FAIL || true)
printf '\nRequests sent during the rolling update: %s | answered by v1: %s | by v2: %s | failed: %s\n' \
  "$((v1 + v2 + failed))" "$v1" "$v2" "$failed"
kubectl delete pod rollout-watch >/dev/null

step "3. Rollback v2 -> v1"
run kubectl rollout history deployment/catalog-service
run kubectl rollout undo deployment/catalog-service
run kubectl rollout status deployment/catalog-service --timeout=120s
run kubectl rollout history deployment/catalog-service
run kubectl get pods -l app=catalog-service
settle
version

step "4. Self-healing: kill a pod (mini Chaos Monkey)"
victim=$(kubectl get pods -l app=catalog-service -o jsonpath='{.items[0].metadata.name}')
run kubectl delete pod "$victim" --wait=false
sleep 2
run kubectl get pods -l app=catalog-service
settle
run kubectl wait --for=condition=Available deployment/catalog-service --timeout=60s
run kubectl get pods -l app=catalog-service
run kubectl get deployment catalog-service
