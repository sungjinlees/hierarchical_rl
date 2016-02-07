

import lasagne
import learning_utils
import numpy as np
import theano
import theano.tensor as T

class QNetwork(object):

    def __init__(self, input_shape, batch_size, num_actions, num_hidden, policy, discount, learning_rate, update_rule, freeze_interval, rng):
        self.input_shape = input_shape
        self.batch_size = batch_size
        self.num_actions = num_actions
        self.num_hidden = num_hidden
        self.policy = policy
        self.discount = discount
        self.learning_rate = learning_rate
        self.update_rule = update_rule
        self.freeze_interval = freeze_interval
        self.rng = rng if rng else np.random.RandomState()
        self.initialize_network()

    def train(self, states, actions, rewards, next_states):
        return 0

    def get_action(self, state):
        """
        :description: returns the action to take given a state. This assumes epsilon greedy
        """
        q_values = get_q_values(state)
        self.policy.choose_action(q_values)

    def get_q_values(self, state):
        states = np.zeros((self.batch_size, self.input_shape), dtype=theano.config.floatX)
        states[0] = state
        self.states_shared.set_value(states)
        q_values = self._get_q_values()[0]
        return q_values

    def get_params(self):
        return lasagne.layers.helper.get_all_param_values(self.l_out)

    def reset_target_network(self):
        all_params = lasagne.layers.helper.get_all_param_values(self.l_out)
        lasagne.layers.helper.set_all_param_values(self.next_l_out, all_params)


    ##########################################################################################
    #### Initialization below this line
    ##########################################################################################

    def initialize_network(self):
        """
        :description: this method initializes the network, updates, and theano functions for training and 
            retrieving q values. Here's an outline: 

            1. build the q network and target q network
            2. initialize theano symbolic variables used for compiling functions
            3. initialize the theano numeric variables used as input to functions
            4. formulate the symbolic loss 
            5. formulate the symbolic updates 
            6. compile theano functions for training and for getting q_values
        """
        batch_size, input_shape = self.batch_size, self.input_shape
        lasagne.random.set_rng(self.rng)

        # 1. build the q network and target q network
        self.l_out = self.build_network(input_shape, self.num_actions, batch_size)
        self.next_l_out = self.build_network(input_shape, self.num_actions, batch_size)
        self.reset_target_network()

        # 2. initialize theano symbolic variables used for compiling functions
        states = T.matrix('states')
        actions = T.icol('actions')
        rewards = T.col('rewards')
        next_states = T.matrix('next_states')
        # terminals are used to indicate a terminal state in the episode and hence a mask over the future
        # q values i.e., Q(s',a')
        terminals = T.icol('terminals')

        # 3. initialize the theano numeric variables used as input to functions
        self.states_shared = theano.shared( np.zeros((batch_size, input_shape), dtype=theano.config.floatX))
        self.next_states_shared = theano.shared(np.zeros((batch_size, input_shape), dtype=theano.config.floatX))
        self.rewards_shared = theano.shared( np.zeros((batch_size, 1), dtype=theano.config.floatX), 
            broadcastable=(False, True))
        self.actions_shared = theano.shared(np.zeros((batch_size, 1), dtype='int32'),
            broadcastable=(False, True))
        self.terminals_shared = theano.shared(np.zeros((batch_size, 1), dtype='int32'),
            broadcastable=(False, True))

        # 4. formulate the symbolic loss 
        q_vals = lasagne.layers.get_output(self.l_out, states)
        next_q_vals = lasagne.layers.get_output(self.next_l_out, next_states)
        target = (rewards +
                 (T.ones_like(terminals) - terminals) *
                  self.discount * T.max(next_q_vals, axis=1, keepdims=True))
        # reshape((-1,)) == 'make a row vector', reshape((-1, 1) == 'make a column vector'
        diff = target - q_vals[T.arange(batch_size), actions.reshape((-1,))].reshape((-1, 1))

        loss = 0.5 * diff ** 2
        loss = T.mean(loss)

        # 5. formulate the symbolic updates 
        params = lasagne.layers.helper.get_all_params(self.l_out)  
        updates = self.initialize_updates(self.update_rule, loss, params, self.learning_rate)

        # 6. compile theano functions for training and for getting q_values
        givens = {
            states: self.states_shared,
            next_states: self.next_states_shared,
            rewards: self.rewards_shared,
            actions: self.actions_shared,
            terminals: self.terminals_shared
        }
        self._train = theano.function([], [loss, q_vals], updates=updates, givens=givens)
        self._get_q_values = theano.function([], q_vals, givens={states: self.states_shared})

    def initialize_updates(self, update_rule, loss, params, learning_rate):
        if update_rule == 'adam':
            updates = lasagne.updates.adam(loss, params, learning_rate)
        elif update_rule == 'rmsprop':
            updates = lasagne.updates.rmsprop(loss, params, learning_rate)
        elif update_rule == 'sgd':
            updates = lasagne.updates.sgd(loss, params, learning_rate)
        else:
            raise ValueError("Unrecognized update: {}".format(update_rule))
        updates = lasagne.updates.apply_momentum(updates)
        return updates

    def build_network(self, input_shape, output_shape, batch_size):

        l_in = lasagne.layers.InputLayer(
            shape=(batch_size, input_shape)
        )

        l_hidden1 = lasagne.layers.DenseLayer(
            l_in,
            num_units=self.num_hidden,
            nonlinearity=lasagne.nonlinearities.rectify,
            W=lasagne.init.HeNormal(),
            b=lasagne.init.Constant(.1)
        )

        l_hidden2 = lasagne.layers.DenseLayer(
            l_hidden1,
            num_units=self.num_hidden,
            nonlinearity=lasagne.nonlinearities.rectify,
            W=lasagne.init.HeNormal(),
            b=lasagne.init.Constant(.1)
        )

        l_out = lasagne.layers.DenseLayer(
            l_hidden2,
            num_units=output_shape,
            nonlinearity=None,
            W=lasagne.init.HeNormal(),
            b=lasagne.init.Constant(.1)
        )

        return l_out

