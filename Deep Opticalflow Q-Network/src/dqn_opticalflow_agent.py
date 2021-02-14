from src.agent import BaseAgent
from src.history import History
from src.replay_memory import DQNReplayMemory
from src.networks.dqn import DQN
import numpy as np
from tqdm import tqdm
import cv2
import random
import pickle
import matplotlib.pyplot as plt
import statistics
import math

class DQNOPTICALFLOWAgent(BaseAgent):

    def __init__(self, config):
        super(DQNOPTICALFLOWAgent, self).__init__(config)
        self.history = History(config)
        self.replay_memory = DQNReplayMemory(config)
        self.net = DQN(self.env_wrapper.action_space.n, config)
        self.net.build()
        self.net.add_summary(["average_reward", "average_loss", "average_q", "ep_max_reward", "ep_min_reward", "ep_num_game", "learning_rate"], ["ep_rewards", "ep_actions"])

# screen 画像を取得してるところで同時に history.add もしてるから, screen を全部重ね合わせ or OpticalFlow 画像にすれば良さげ(84×84)
    def observe(self):
        reward = max(self.min_reward, min(self.max_reward, self.env_wrapper.reward))
        screen = self.env_wrapper.screen    # グレースケールの画像取得 84*84 のFlickering済画像取得
        screen = cv2.addWeighted(screen, 1.0, self.history.get()[-1], 0.5, 0)
        self.history.add(screen)            # hiistoryに追加
        self.replay_memory.add(screen, reward, self.env_wrapper.action, self.env_wrapper.terminal)  # replaay_memoryに行動と報酬と画像を紐付けて保存
        if self.i < self.config.epsilon_decay_episodes:
            self.epsilon -= self.config.epsilon_decay
        if self.i % self.config.train_freq == 0 and self.i > self.config.train_start:
            state, action, reward, state_, terminal = self.replay_memory.sample_batch()
            q, loss= self.net.train_on_batch_target(state, action, reward, state_, terminal, self.i)
            self.total_q += q
            self.total_loss += loss
            self.update_count += 1
        if self.i % self.config.update_freq == 0:
            self.net.update_target()

    def policy(self):
        if np.random.rand() < self.epsilon:
            return self.env_wrapper.random_step()
        else:
            state = self.history.get()/255.0
            a = self.net.q_action.eval({
                self.net.state : [state]
            }, session=self.net.sess)
            return a[0]


    def train(self, steps):
        render = False
        self.env_wrapper.new_random_game()
        num_game, self.update_count, ep_reward = 0,0,0.
        total_reward, self.total_loss, self.total_q = 0.,0.,0.
        ep_rewards, actions = [], []
        t = 0

        for _ in range(self.config.history_len):
            screen = self.env_wrapper.screen    # グレースケールの画像取得 84*84 のFlickering済画像取得
            screen = cv2.addWeighted(screen, 1.0, self.history.get()[-1], 0.5, 0)
            self.history.add(screen)            # hiistoryに追加
        for self.i in tqdm(range(self.i, steps)):
            action = self.policy()
            self.env_wrapper.act(action)
            self.observe()
            if self.env_wrapper.terminal:       # terminal で, ゲームが終了したかどうかが格納されてる（gymのdoneと同じ）
                t = 0
                self.env_wrapper.new_random_game()
                num_game += 1
                ep_rewards.append(ep_reward)
                ep_reward = 0.
            else:
                ep_reward += self.env_wrapper.reward    # epsode ごとの報酬を格納
                t += 1
            actions.append(action)
            total_reward += self.env_wrapper.reward

            if self.i >= self.config.train_start:
                if self.i % self.config.test_step == self.config.test_step -1:
                    avg_reward = total_reward / self.config.test_step
                    avg_loss = self.total_loss / self.update_count
                    avg_q = self.total_q / self.update_count

                    try:
                        max_ep_reward = np.max(ep_rewards)
                        min_ep_reward = np.min(ep_rewards)
                        avg_ep_reward = np.mean(ep_rewards)
                    except:
                        max_ep_reward, min_ep_reward, avg_ep_reward = 0, 0, 0

                    sum_dict = {
                        'average_reward': avg_reward,
                        'average_loss': avg_loss,
                        'average_q': avg_q,
                        'ep_max_reward': max_ep_reward,
                        'ep_min_reward': min_ep_reward,
                        'ep_num_game': num_game,
                        'learning_rate': self.net.learning_rate,
                        'ep_rewards': ep_rewards,
                        'ep_actions': actions
                    }
                    self.net.inject_summary(sum_dict, self.i)
                    num_game = 0
                    total_reward = 0.
                    self.total_loss = 0.
                    self.total_q = 0.
                    self.update_count = 0
                    ep_reward = 0.
                    ep_rewards = []
                    actions = []

            if self.i % 500000 == 0 and self.i > 0:
                j = 0
                self.save()
            if self.i % 100000 == 0:
                j = 0
                render = True

            if render:
                #self.env_wrapper.env.render()
                j += 1
                if j == 1000:
                    render = False

    def play(self, episodes, net_path):
        self.net.restore_session(path=net_path)
        self.env_wrapper.new_game()
        for _ in range(self.config.history_len):
            screen = self.env_wrapper.screen
            screen = cv2.addWeighted(screen, 1.0, self.history.get()[-1], 0.5, 0)
            self.history.add(screen)
        episode_steps = 0
        #####
        total_reward = []
        episode_reward = 0
        p = []
        episode_count_list = []
        for i in tqdm(np.arange(0, 1.1, 0.1)):
            self.config.flickering_p = i
            episode_count = 0
            total_episode_reward = []
        #####
            episodes = 5000
            for _ in (range(episodes)):
                a = self.net.q_action.eval({
                self.net.state : [self.history.get()/255.0]
                }, session=self.net.sess)
                action = a[0]
                self.env_wrapper.act_play(action)
                screen = self.env_wrapper.screen
                screen = cv2.addWeighted(screen, 1.0, self.history.get()[-1], 0.5, 0)
                self.history.add(screen)
                episode_steps += 1
                #####
                episode_reward += self.env_wrapper.reward
                #####
                if episode_steps > self.config.max_steps:
                    self.env_wrapper.terminal = True
                if self.env_wrapper.terminal:
                    episode_steps = 0
                    #####
                    total_episode_reward.append(episode_reward)
                    episode_reward = 0
                    episode_count += 1
                    #####
                    self.env_wrapper.new_play_game()
                    for _ in range(self.config.history_len):
                        screen = self.env_wrapper.screen
                        screen = cv2.addWeighted(screen, 1.0, self.history.get()[-1], 0.5, 0)
                        self.history.add(screen)
            #####
            p.append(i)
            total_reward.append(max(total_episode_reward))
            print(total_reward)
#            total_reward.append(statistics.mean(total_episode_reward))
            episode_count_list.append(episode_count)
            #####
        ###        
        print(total_reward, self.config.flickering_p)
        self.config.flickering_p = 1.0
        print(self.config.flickering_p)
        self.plot_value(total_reward, p)

    def plot_value(self, score, p):
        iteration = p
        plt.title("Test Plot")
        plt.xlabel("Flickering Probability")
        plt.ylabel("Score")
        plt.plot(iteration, score, linewidth=0.7)
        plt.show()
        ###