from flask import Flask, render_template, jsonify
import threading
import time
import random
from collections import deque

app = Flask(__name__)

# 全局状态
philosophers = [0] * 5      # 0:思考, 1:等待(饥饿), 2:吃饭
eat_counts = [0] * 5
stop_event = threading.Event()
threads = []

# 筷子锁
chopsticks = [threading.Lock() for _ in range(5)]

# 服务员队列 (FIFO)
waiter_queue = deque()
queue_lock = threading.Lock()


def philosopher_waiter(pid):
    """服务员解法：公平队列 + 全局互斥锁 (一次只允许一人进餐)"""
    left = pid
    right = (pid + 1) % 5
    # 随机错开启动时间
    time.sleep(random.uniform(0, 1))

    while not stop_event.is_set():
        # 1. 思考 (随机时长)
        philosophers[pid] = 0
        if stop_event.wait(timeout=random.uniform(0.8, 2.5)):
            break

        # 2. 饥饿，加入队列
        philosophers[pid] = 1
        with queue_lock:
            waiter_queue.append(pid)

        # 3. 等待叫号 (直到队列头部是自己)
        while not stop_event.is_set():
            with queue_lock:
                if waiter_queue and waiter_queue[0] == pid:
                    waiter_queue.popleft()
                    break
            # 短暂等待，同时可响应停止事件
            if stop_event.wait(timeout=0.05):
                # 被中断时将自己从队列中移除（如果还在）
                with queue_lock:
                    if pid in waiter_queue:
                        waiter_queue.remove(pid)
                return

        if stop_event.is_set():
            break

        # 4. 拿起两根筷子 (可中断的超时重试)
        while not stop_event.is_set():
            if chopsticks[left].acquire(timeout=0.1):
                if chopsticks[right].acquire(timeout=0.1):
                    break
                chopsticks[left].release()
        if stop_event.is_set():
            # 释放可能已持有的锁
            chopsticks[right].release()
            chopsticks[left].release()
            break

        # 5. 吃饭 (随机时长)
        philosophers[pid] = 2
        eat_counts[pid] += 1
        if stop_event.wait(timeout=random.uniform(0.6, 1.8)):
            # 吃饭中被中断，释放筷子后退出
            chopsticks[right].release()
            chopsticks[left].release()
            break

        # 6. 放下筷子
        chopsticks[right].release()
        chopsticks[left].release()


def start_simulation():
    """启动5个哲学家线程"""
    global threads
    stop_event.clear()
    for i in range(5):
        t = threading.Thread(target=philosopher_waiter, args=(i,), daemon=True)
        threads.append(t)
        t.start()


def stop_simulation():
    """停止所有线程并清理"""
    stop_event.set()
    for t in threads:
        t.join(timeout=1.0)
    threads.clear()
    # 重置全局状态
    global philosophers, eat_counts, waiter_queue, chopsticks
    philosophers = [0] * 5
    eat_counts = [0] * 5
    waiter_queue = deque()
    chopsticks = [threading.Lock() for _ in range(5)]


# 默认启动
start_simulation()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/status')
def status():
    return jsonify({
        'philosophers': philosophers,
        'eat_counts': eat_counts
    })


@app.route('/reset')
def reset():
    """重置模拟 (停止所有线程并重新开始)"""
    stop_simulation()
    start_simulation()
    return jsonify(msg="ok")


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)