set_option autoImplicit false
set_option maxRecDepth 20000
set_option maxHeartbeats 2000000

namespace Model

abbrev Cell : Type := Option (BitVec 8)

abbrev Bytes : Type := List Cell

structure R_BatchHeaderV0 where
  f_BatchIndex_0 : BitVec 8
  f_BatchIndex_1 : BitVec 8
  f_BatchIndex_2 : BitVec 8
  f_BatchIndex_3 : BitVec 8
  f_BatchIndex_4 : BitVec 8
  f_BatchIndex_5 : BitVec 8
  f_BatchIndex_6 : BitVec 8
  f_BatchIndex_7 : BitVec 8
  f_L1MessagePopped_0 : BitVec 8
  f_L1MessagePopped_1 : BitVec 8
  f_L1MessagePopped_2 : BitVec 8
  f_L1MessagePopped_3 : BitVec 8
  f_L1MessagePopped_4 : BitVec 8
  f_L1MessagePopped_5 : BitVec 8
  f_L1MessagePopped_6 : BitVec 8
  f_L1MessagePopped_7 : BitVec 8
  f_TotalL1MessagePopped_0 : BitVec 8
  f_TotalL1MessagePopped_1 : BitVec 8
  f_TotalL1MessagePopped_2 : BitVec 8
  f_TotalL1MessagePopped_3 : BitVec 8
  f_TotalL1MessagePopped_4 : BitVec 8
  f_TotalL1MessagePopped_5 : BitVec 8
  f_TotalL1MessagePopped_6 : BitVec 8
  f_TotalL1MessagePopped_7 : BitVec 8
  f_DataHash_0 : BitVec 8
  f_DataHash_1 : BitVec 8
  f_DataHash_2 : BitVec 8
  f_DataHash_3 : BitVec 8
  f_DataHash_4 : BitVec 8
  f_DataHash_5 : BitVec 8
  f_DataHash_6 : BitVec 8
  f_DataHash_7 : BitVec 8
  f_DataHash_8 : BitVec 8
  f_DataHash_9 : BitVec 8
  f_DataHash_10 : BitVec 8
  f_DataHash_11 : BitVec 8
  f_DataHash_12 : BitVec 8
  f_DataHash_13 : BitVec 8
  f_DataHash_14 : BitVec 8
  f_DataHash_15 : BitVec 8
  f_DataHash_16 : BitVec 8
  f_DataHash_17 : BitVec 8
  f_DataHash_18 : BitVec 8
  f_DataHash_19 : BitVec 8
  f_DataHash_20 : BitVec 8
  f_DataHash_21 : BitVec 8
  f_DataHash_22 : BitVec 8
  f_DataHash_23 : BitVec 8
  f_DataHash_24 : BitVec 8
  f_DataHash_25 : BitVec 8
  f_DataHash_26 : BitVec 8
  f_DataHash_27 : BitVec 8
  f_DataHash_28 : BitVec 8
  f_DataHash_29 : BitVec 8
  f_DataHash_30 : BitVec 8
  f_DataHash_31 : BitVec 8
  f_BlobVersionedHash_0 : BitVec 8
  f_BlobVersionedHash_1 : BitVec 8
  f_BlobVersionedHash_2 : BitVec 8
  f_BlobVersionedHash_3 : BitVec 8
  f_BlobVersionedHash_4 : BitVec 8
  f_BlobVersionedHash_5 : BitVec 8
  f_BlobVersionedHash_6 : BitVec 8
  f_BlobVersionedHash_7 : BitVec 8
  f_BlobVersionedHash_8 : BitVec 8
  f_BlobVersionedHash_9 : BitVec 8
  f_BlobVersionedHash_10 : BitVec 8
  f_BlobVersionedHash_11 : BitVec 8
  f_BlobVersionedHash_12 : BitVec 8
  f_BlobVersionedHash_13 : BitVec 8
  f_BlobVersionedHash_14 : BitVec 8
  f_BlobVersionedHash_15 : BitVec 8
  f_BlobVersionedHash_16 : BitVec 8
  f_BlobVersionedHash_17 : BitVec 8
  f_BlobVersionedHash_18 : BitVec 8
  f_BlobVersionedHash_19 : BitVec 8
  f_BlobVersionedHash_20 : BitVec 8
  f_BlobVersionedHash_21 : BitVec 8
  f_BlobVersionedHash_22 : BitVec 8
  f_BlobVersionedHash_23 : BitVec 8
  f_BlobVersionedHash_24 : BitVec 8
  f_BlobVersionedHash_25 : BitVec 8
  f_BlobVersionedHash_26 : BitVec 8
  f_BlobVersionedHash_27 : BitVec 8
  f_BlobVersionedHash_28 : BitVec 8
  f_BlobVersionedHash_29 : BitVec 8
  f_BlobVersionedHash_30 : BitVec 8
  f_BlobVersionedHash_31 : BitVec 8
  f_PrevStateRoot_0 : BitVec 8
  f_PrevStateRoot_1 : BitVec 8
  f_PrevStateRoot_2 : BitVec 8
  f_PrevStateRoot_3 : BitVec 8
  f_PrevStateRoot_4 : BitVec 8
  f_PrevStateRoot_5 : BitVec 8
  f_PrevStateRoot_6 : BitVec 8
  f_PrevStateRoot_7 : BitVec 8
  f_PrevStateRoot_8 : BitVec 8
  f_PrevStateRoot_9 : BitVec 8
  f_PrevStateRoot_10 : BitVec 8
  f_PrevStateRoot_11 : BitVec 8
  f_PrevStateRoot_12 : BitVec 8
  f_PrevStateRoot_13 : BitVec 8
  f_PrevStateRoot_14 : BitVec 8
  f_PrevStateRoot_15 : BitVec 8
  f_PrevStateRoot_16 : BitVec 8
  f_PrevStateRoot_17 : BitVec 8
  f_PrevStateRoot_18 : BitVec 8
  f_PrevStateRoot_19 : BitVec 8
  f_PrevStateRoot_20 : BitVec 8
  f_PrevStateRoot_21 : BitVec 8
  f_PrevStateRoot_22 : BitVec 8
  f_PrevStateRoot_23 : BitVec 8
  f_PrevStateRoot_24 : BitVec 8
  f_PrevStateRoot_25 : BitVec 8
  f_PrevStateRoot_26 : BitVec 8
  f_PrevStateRoot_27 : BitVec 8
  f_PrevStateRoot_28 : BitVec 8
  f_PrevStateRoot_29 : BitVec 8
  f_PrevStateRoot_30 : BitVec 8
  f_PrevStateRoot_31 : BitVec 8
  f_PostStateRoot_0 : BitVec 8
  f_PostStateRoot_1 : BitVec 8
  f_PostStateRoot_2 : BitVec 8
  f_PostStateRoot_3 : BitVec 8
  f_PostStateRoot_4 : BitVec 8
  f_PostStateRoot_5 : BitVec 8
  f_PostStateRoot_6 : BitVec 8
  f_PostStateRoot_7 : BitVec 8
  f_PostStateRoot_8 : BitVec 8
  f_PostStateRoot_9 : BitVec 8
  f_PostStateRoot_10 : BitVec 8
  f_PostStateRoot_11 : BitVec 8
  f_PostStateRoot_12 : BitVec 8
  f_PostStateRoot_13 : BitVec 8
  f_PostStateRoot_14 : BitVec 8
  f_PostStateRoot_15 : BitVec 8
  f_PostStateRoot_16 : BitVec 8
  f_PostStateRoot_17 : BitVec 8
  f_PostStateRoot_18 : BitVec 8
  f_PostStateRoot_19 : BitVec 8
  f_PostStateRoot_20 : BitVec 8
  f_PostStateRoot_21 : BitVec 8
  f_PostStateRoot_22 : BitVec 8
  f_PostStateRoot_23 : BitVec 8
  f_PostStateRoot_24 : BitVec 8
  f_PostStateRoot_25 : BitVec 8
  f_PostStateRoot_26 : BitVec 8
  f_PostStateRoot_27 : BitVec 8
  f_PostStateRoot_28 : BitVec 8
  f_PostStateRoot_29 : BitVec 8
  f_PostStateRoot_30 : BitVec 8
  f_PostStateRoot_31 : BitVec 8
  f_WithdrawalRoot_0 : BitVec 8
  f_WithdrawalRoot_1 : BitVec 8
  f_WithdrawalRoot_2 : BitVec 8
  f_WithdrawalRoot_3 : BitVec 8
  f_WithdrawalRoot_4 : BitVec 8
  f_WithdrawalRoot_5 : BitVec 8
  f_WithdrawalRoot_6 : BitVec 8
  f_WithdrawalRoot_7 : BitVec 8
  f_WithdrawalRoot_8 : BitVec 8
  f_WithdrawalRoot_9 : BitVec 8
  f_WithdrawalRoot_10 : BitVec 8
  f_WithdrawalRoot_11 : BitVec 8
  f_WithdrawalRoot_12 : BitVec 8
  f_WithdrawalRoot_13 : BitVec 8
  f_WithdrawalRoot_14 : BitVec 8
  f_WithdrawalRoot_15 : BitVec 8
  f_WithdrawalRoot_16 : BitVec 8
  f_WithdrawalRoot_17 : BitVec 8
  f_WithdrawalRoot_18 : BitVec 8
  f_WithdrawalRoot_19 : BitVec 8
  f_WithdrawalRoot_20 : BitVec 8
  f_WithdrawalRoot_21 : BitVec 8
  f_WithdrawalRoot_22 : BitVec 8
  f_WithdrawalRoot_23 : BitVec 8
  f_WithdrawalRoot_24 : BitVec 8
  f_WithdrawalRoot_25 : BitVec 8
  f_WithdrawalRoot_26 : BitVec 8
  f_WithdrawalRoot_27 : BitVec 8
  f_WithdrawalRoot_28 : BitVec 8
  f_WithdrawalRoot_29 : BitVec 8
  f_WithdrawalRoot_30 : BitVec 8
  f_WithdrawalRoot_31 : BitVec 8
  f_SequencerSetVerifyHash_0 : BitVec 8
  f_SequencerSetVerifyHash_1 : BitVec 8
  f_SequencerSetVerifyHash_2 : BitVec 8
  f_SequencerSetVerifyHash_3 : BitVec 8
  f_SequencerSetVerifyHash_4 : BitVec 8
  f_SequencerSetVerifyHash_5 : BitVec 8
  f_SequencerSetVerifyHash_6 : BitVec 8
  f_SequencerSetVerifyHash_7 : BitVec 8
  f_SequencerSetVerifyHash_8 : BitVec 8
  f_SequencerSetVerifyHash_9 : BitVec 8
  f_SequencerSetVerifyHash_10 : BitVec 8
  f_SequencerSetVerifyHash_11 : BitVec 8
  f_SequencerSetVerifyHash_12 : BitVec 8
  f_SequencerSetVerifyHash_13 : BitVec 8
  f_SequencerSetVerifyHash_14 : BitVec 8
  f_SequencerSetVerifyHash_15 : BitVec 8
  f_SequencerSetVerifyHash_16 : BitVec 8
  f_SequencerSetVerifyHash_17 : BitVec 8
  f_SequencerSetVerifyHash_18 : BitVec 8
  f_SequencerSetVerifyHash_19 : BitVec 8
  f_SequencerSetVerifyHash_20 : BitVec 8
  f_SequencerSetVerifyHash_21 : BitVec 8
  f_SequencerSetVerifyHash_22 : BitVec 8
  f_SequencerSetVerifyHash_23 : BitVec 8
  f_SequencerSetVerifyHash_24 : BitVec 8
  f_SequencerSetVerifyHash_25 : BitVec 8
  f_SequencerSetVerifyHash_26 : BitVec 8
  f_SequencerSetVerifyHash_27 : BitVec 8
  f_SequencerSetVerifyHash_28 : BitVec 8
  f_SequencerSetVerifyHash_29 : BitVec 8
  f_SequencerSetVerifyHash_30 : BitVec 8
  f_SequencerSetVerifyHash_31 : BitVec 8
  f_ParentBatchHash_0 : BitVec 8
  f_ParentBatchHash_1 : BitVec 8
  f_ParentBatchHash_2 : BitVec 8
  f_ParentBatchHash_3 : BitVec 8
  f_ParentBatchHash_4 : BitVec 8
  f_ParentBatchHash_5 : BitVec 8
  f_ParentBatchHash_6 : BitVec 8
  f_ParentBatchHash_7 : BitVec 8
  f_ParentBatchHash_8 : BitVec 8
  f_ParentBatchHash_9 : BitVec 8
  f_ParentBatchHash_10 : BitVec 8
  f_ParentBatchHash_11 : BitVec 8
  f_ParentBatchHash_12 : BitVec 8
  f_ParentBatchHash_13 : BitVec 8
  f_ParentBatchHash_14 : BitVec 8
  f_ParentBatchHash_15 : BitVec 8
  f_ParentBatchHash_16 : BitVec 8
  f_ParentBatchHash_17 : BitVec 8
  f_ParentBatchHash_18 : BitVec 8
  f_ParentBatchHash_19 : BitVec 8
  f_ParentBatchHash_20 : BitVec 8
  f_ParentBatchHash_21 : BitVec 8
  f_ParentBatchHash_22 : BitVec 8
  f_ParentBatchHash_23 : BitVec 8
  f_ParentBatchHash_24 : BitVec 8
  f_ParentBatchHash_25 : BitVec 8
  f_ParentBatchHash_26 : BitVec 8
  f_ParentBatchHash_27 : BitVec 8
  f_ParentBatchHash_28 : BitVec 8
  f_ParentBatchHash_29 : BitVec 8
  f_ParentBatchHash_30 : BitVec 8
  f_ParentBatchHash_31 : BitVec 8

structure R_BatchHeaderV1 where
  f_BatchHeaderV0__BatchIndex_0 : BitVec 8
  f_BatchHeaderV0__BatchIndex_1 : BitVec 8
  f_BatchHeaderV0__BatchIndex_2 : BitVec 8
  f_BatchHeaderV0__BatchIndex_3 : BitVec 8
  f_BatchHeaderV0__BatchIndex_4 : BitVec 8
  f_BatchHeaderV0__BatchIndex_5 : BitVec 8
  f_BatchHeaderV0__BatchIndex_6 : BitVec 8
  f_BatchHeaderV0__BatchIndex_7 : BitVec 8
  f_BatchHeaderV0__L1MessagePopped_0 : BitVec 8
  f_BatchHeaderV0__L1MessagePopped_1 : BitVec 8
  f_BatchHeaderV0__L1MessagePopped_2 : BitVec 8
  f_BatchHeaderV0__L1MessagePopped_3 : BitVec 8
  f_BatchHeaderV0__L1MessagePopped_4 : BitVec 8
  f_BatchHeaderV0__L1MessagePopped_5 : BitVec 8
  f_BatchHeaderV0__L1MessagePopped_6 : BitVec 8
  f_BatchHeaderV0__L1MessagePopped_7 : BitVec 8
  f_BatchHeaderV0__TotalL1MessagePopped_0 : BitVec 8
  f_BatchHeaderV0__TotalL1MessagePopped_1 : BitVec 8
  f_BatchHeaderV0__TotalL1MessagePopped_2 : BitVec 8
  f_BatchHeaderV0__TotalL1MessagePopped_3 : BitVec 8
  f_BatchHeaderV0__TotalL1MessagePopped_4 : BitVec 8
  f_BatchHeaderV0__TotalL1MessagePopped_5 : BitVec 8
  f_BatchHeaderV0__TotalL1MessagePopped_6 : BitVec 8
  f_BatchHeaderV0__TotalL1MessagePopped_7 : BitVec 8
  f_BatchHeaderV0__DataHash_0 : BitVec 8
  f_BatchHeaderV0__DataHash_1 : BitVec 8
  f_BatchHeaderV0__DataHash_2 : BitVec 8
  f_BatchHeaderV0__DataHash_3 : BitVec 8
  f_BatchHeaderV0__DataHash_4 : BitVec 8
  f_BatchHeaderV0__DataHash_5 : BitVec 8
  f_BatchHeaderV0__DataHash_6 : BitVec 8
  f_BatchHeaderV0__DataHash_7 : BitVec 8
  f_BatchHeaderV0__DataHash_8 : BitVec 8
  f_BatchHeaderV0__DataHash_9 : BitVec 8
  f_BatchHeaderV0__DataHash_10 : BitVec 8
  f_BatchHeaderV0__DataHash_11 : BitVec 8
  f_BatchHeaderV0__DataHash_12 : BitVec 8
  f_BatchHeaderV0__DataHash_13 : BitVec 8
  f_BatchHeaderV0__DataHash_14 : BitVec 8
  f_BatchHeaderV0__DataHash_15 : BitVec 8
  f_BatchHeaderV0__DataHash_16 : BitVec 8
  f_BatchHeaderV0__DataHash_17 : BitVec 8
  f_BatchHeaderV0__DataHash_18 : BitVec 8
  f_BatchHeaderV0__DataHash_19 : BitVec 8
  f_BatchHeaderV0__DataHash_20 : BitVec 8
  f_BatchHeaderV0__DataHash_21 : BitVec 8
  f_BatchHeaderV0__DataHash_22 : BitVec 8
  f_BatchHeaderV0__DataHash_23 : BitVec 8
  f_BatchHeaderV0__DataHash_24 : BitVec 8
  f_BatchHeaderV0__DataHash_25 : BitVec 8
  f_BatchHeaderV0__DataHash_26 : BitVec 8
  f_BatchHeaderV0__DataHash_27 : BitVec 8
  f_BatchHeaderV0__DataHash_28 : BitVec 8
  f_BatchHeaderV0__DataHash_29 : BitVec 8
  f_BatchHeaderV0__DataHash_30 : BitVec 8
  f_BatchHeaderV0__DataHash_31 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_0 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_1 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_2 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_3 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_4 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_5 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_6 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_7 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_8 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_9 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_10 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_11 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_12 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_13 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_14 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_15 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_16 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_17 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_18 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_19 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_20 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_21 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_22 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_23 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_24 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_25 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_26 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_27 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_28 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_29 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_30 : BitVec 8
  f_BatchHeaderV0__BlobVersionedHash_31 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_0 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_1 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_2 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_3 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_4 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_5 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_6 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_7 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_8 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_9 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_10 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_11 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_12 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_13 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_14 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_15 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_16 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_17 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_18 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_19 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_20 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_21 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_22 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_23 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_24 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_25 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_26 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_27 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_28 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_29 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_30 : BitVec 8
  f_BatchHeaderV0__PrevStateRoot_31 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_0 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_1 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_2 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_3 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_4 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_5 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_6 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_7 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_8 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_9 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_10 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_11 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_12 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_13 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_14 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_15 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_16 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_17 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_18 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_19 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_20 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_21 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_22 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_23 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_24 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_25 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_26 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_27 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_28 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_29 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_30 : BitVec 8
  f_BatchHeaderV0__PostStateRoot_31 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_0 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_1 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_2 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_3 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_4 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_5 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_6 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_7 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_8 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_9 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_10 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_11 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_12 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_13 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_14 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_15 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_16 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_17 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_18 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_19 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_20 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_21 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_22 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_23 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_24 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_25 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_26 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_27 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_28 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_29 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_30 : BitVec 8
  f_BatchHeaderV0__WithdrawalRoot_31 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_0 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_1 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_2 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_3 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_4 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_5 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_6 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_7 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_8 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_9 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_10 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_11 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_12 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_13 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_14 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_15 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_16 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_17 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_18 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_19 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_20 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_21 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_22 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_23 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_24 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_25 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_26 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_27 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_28 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_29 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_30 : BitVec 8
  f_BatchHeaderV0__SequencerSetVerifyHash_31 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_0 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_1 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_2 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_3 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_4 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_5 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_6 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_7 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_8 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_9 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_10 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_11 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_12 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_13 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_14 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_15 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_16 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_17 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_18 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_19 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_20 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_21 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_22 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_23 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_24 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_25 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_26 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_27 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_28 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_29 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_30 : BitVec 8
  f_BatchHeaderV0__ParentBatchHash_31 : BitVec 8
  f_LastBlockNumber_0 : BitVec 8
  f_LastBlockNumber_1 : BitVec 8
  f_LastBlockNumber_2 : BitVec 8
  f_LastBlockNumber_3 : BitVec 8
  f_LastBlockNumber_4 : BitVec 8
  f_LastBlockNumber_5 : BitVec 8
  f_LastBlockNumber_6 : BitVec 8
  f_LastBlockNumber_7 : BitVec 8

structure R_Header where
  f_version_0 : BitVec 8
  f_batchIndex_0 : BitVec 8
  f_batchIndex_1 : BitVec 8
  f_batchIndex_2 : BitVec 8
  f_batchIndex_3 : BitVec 8
  f_batchIndex_4 : BitVec 8
  f_batchIndex_5 : BitVec 8
  f_batchIndex_6 : BitVec 8
  f_batchIndex_7 : BitVec 8
  f_l1MessagePopped_0 : BitVec 8
  f_l1MessagePopped_1 : BitVec 8
  f_l1MessagePopped_2 : BitVec 8
  f_l1MessagePopped_3 : BitVec 8
  f_l1MessagePopped_4 : BitVec 8
  f_l1MessagePopped_5 : BitVec 8
  f_l1MessagePopped_6 : BitVec 8
  f_l1MessagePopped_7 : BitVec 8
  f_totalL1MessagePopped_0 : BitVec 8
  f_totalL1MessagePopped_1 : BitVec 8
  f_totalL1MessagePopped_2 : BitVec 8
  f_totalL1MessagePopped_3 : BitVec 8
  f_totalL1MessagePopped_4 : BitVec 8
  f_totalL1MessagePopped_5 : BitVec 8
  f_totalL1MessagePopped_6 : BitVec 8
  f_totalL1MessagePopped_7 : BitVec 8
  f_dataHash_0 : BitVec 8
  f_dataHash_1 : BitVec 8
  f_dataHash_2 : BitVec 8
  f_dataHash_3 : BitVec 8
  f_dataHash_4 : BitVec 8
  f_dataHash_5 : BitVec 8
  f_dataHash_6 : BitVec 8
  f_dataHash_7 : BitVec 8
  f_dataHash_8 : BitVec 8
  f_dataHash_9 : BitVec 8
  f_dataHash_10 : BitVec 8
  f_dataHash_11 : BitVec 8
  f_dataHash_12 : BitVec 8
  f_dataHash_13 : BitVec 8
  f_dataHash_14 : BitVec 8
  f_dataHash_15 : BitVec 8
  f_dataHash_16 : BitVec 8
  f_dataHash_17 : BitVec 8
  f_dataHash_18 : BitVec 8
  f_dataHash_19 : BitVec 8
  f_dataHash_20 : BitVec 8
  f_dataHash_21 : BitVec 8
  f_dataHash_22 : BitVec 8
  f_dataHash_23 : BitVec 8
  f_dataHash_24 : BitVec 8
  f_dataHash_25 : BitVec 8
  f_dataHash_26 : BitVec 8
  f_dataHash_27 : BitVec 8
  f_dataHash_28 : BitVec 8
  f_dataHash_29 : BitVec 8
  f_dataHash_30 : BitVec 8
  f_dataHash_31 : BitVec 8
  f_blobVersionedHash_0 : BitVec 8
  f_blobVersionedHash_1 : BitVec 8
  f_blobVersionedHash_2 : BitVec 8
  f_blobVersionedHash_3 : BitVec 8
  f_blobVersionedHash_4 : BitVec 8
  f_blobVersionedHash_5 : BitVec 8
  f_blobVersionedHash_6 : BitVec 8
  f_blobVersionedHash_7 : BitVec 8
  f_blobVersionedHash_8 : BitVec 8
  f_blobVersionedHash_9 : BitVec 8
  f_blobVersionedHash_10 : BitVec 8
  f_blobVersionedHash_11 : BitVec 8
  f_blobVersionedHash_12 : BitVec 8
  f_blobVersionedHash_13 : BitVec 8
  f_blobVersionedHash_14 : BitVec 8
  f_blobVersionedHash_15 : BitVec 8
  f_blobVersionedHash_16 : BitVec 8
  f_blobVersionedHash_17 : BitVec 8
  f_blobVersionedHash_18 : BitVec 8
  f_blobVersionedHash_19 : BitVec 8
  f_blobVersionedHash_20 : BitVec 8
  f_blobVersionedHash_21 : BitVec 8
  f_blobVersionedHash_22 : BitVec 8
  f_blobVersionedHash_23 : BitVec 8
  f_blobVersionedHash_24 : BitVec 8
  f_blobVersionedHash_25 : BitVec 8
  f_blobVersionedHash_26 : BitVec 8
  f_blobVersionedHash_27 : BitVec 8
  f_blobVersionedHash_28 : BitVec 8
  f_blobVersionedHash_29 : BitVec 8
  f_blobVersionedHash_30 : BitVec 8
  f_blobVersionedHash_31 : BitVec 8
  f_prevStateHash_0 : BitVec 8
  f_prevStateHash_1 : BitVec 8
  f_prevStateHash_2 : BitVec 8
  f_prevStateHash_3 : BitVec 8
  f_prevStateHash_4 : BitVec 8
  f_prevStateHash_5 : BitVec 8
  f_prevStateHash_6 : BitVec 8
  f_prevStateHash_7 : BitVec 8
  f_prevStateHash_8 : BitVec 8
  f_prevStateHash_9 : BitVec 8
  f_prevStateHash_10 : BitVec 8
  f_prevStateHash_11 : BitVec 8
  f_prevStateHash_12 : BitVec 8
  f_prevStateHash_13 : BitVec 8
  f_prevStateHash_14 : BitVec 8
  f_prevStateHash_15 : BitVec 8
  f_prevStateHash_16 : BitVec 8
  f_prevStateHash_17 : BitVec 8
  f_prevStateHash_18 : BitVec 8
  f_prevStateHash_19 : BitVec 8
  f_prevStateHash_20 : BitVec 8
  f_prevStateHash_21 : BitVec 8
  f_prevStateHash_22 : BitVec 8
  f_prevStateHash_23 : BitVec 8
  f_prevStateHash_24 : BitVec 8
  f_prevStateHash_25 : BitVec 8
  f_prevStateHash_26 : BitVec 8
  f_prevStateHash_27 : BitVec 8
  f_prevStateHash_28 : BitVec 8
  f_prevStateHash_29 : BitVec 8
  f_prevStateHash_30 : BitVec 8
  f_prevStateHash_31 : BitVec 8
  f_postStateHash_0 : BitVec 8
  f_postStateHash_1 : BitVec 8
  f_postStateHash_2 : BitVec 8
  f_postStateHash_3 : BitVec 8
  f_postStateHash_4 : BitVec 8
  f_postStateHash_5 : BitVec 8
  f_postStateHash_6 : BitVec 8
  f_postStateHash_7 : BitVec 8
  f_postStateHash_8 : BitVec 8
  f_postStateHash_9 : BitVec 8
  f_postStateHash_10 : BitVec 8
  f_postStateHash_11 : BitVec 8
  f_postStateHash_12 : BitVec 8
  f_postStateHash_13 : BitVec 8
  f_postStateHash_14 : BitVec 8
  f_postStateHash_15 : BitVec 8
  f_postStateHash_16 : BitVec 8
  f_postStateHash_17 : BitVec 8
  f_postStateHash_18 : BitVec 8
  f_postStateHash_19 : BitVec 8
  f_postStateHash_20 : BitVec 8
  f_postStateHash_21 : BitVec 8
  f_postStateHash_22 : BitVec 8
  f_postStateHash_23 : BitVec 8
  f_postStateHash_24 : BitVec 8
  f_postStateHash_25 : BitVec 8
  f_postStateHash_26 : BitVec 8
  f_postStateHash_27 : BitVec 8
  f_postStateHash_28 : BitVec 8
  f_postStateHash_29 : BitVec 8
  f_postStateHash_30 : BitVec 8
  f_postStateHash_31 : BitVec 8
  f_withdrawRootHash_0 : BitVec 8
  f_withdrawRootHash_1 : BitVec 8
  f_withdrawRootHash_2 : BitVec 8
  f_withdrawRootHash_3 : BitVec 8
  f_withdrawRootHash_4 : BitVec 8
  f_withdrawRootHash_5 : BitVec 8
  f_withdrawRootHash_6 : BitVec 8
  f_withdrawRootHash_7 : BitVec 8
  f_withdrawRootHash_8 : BitVec 8
  f_withdrawRootHash_9 : BitVec 8
  f_withdrawRootHash_10 : BitVec 8
  f_withdrawRootHash_11 : BitVec 8
  f_withdrawRootHash_12 : BitVec 8
  f_withdrawRootHash_13 : BitVec 8
  f_withdrawRootHash_14 : BitVec 8
  f_withdrawRootHash_15 : BitVec 8
  f_withdrawRootHash_16 : BitVec 8
  f_withdrawRootHash_17 : BitVec 8
  f_withdrawRootHash_18 : BitVec 8
  f_withdrawRootHash_19 : BitVec 8
  f_withdrawRootHash_20 : BitVec 8
  f_withdrawRootHash_21 : BitVec 8
  f_withdrawRootHash_22 : BitVec 8
  f_withdrawRootHash_23 : BitVec 8
  f_withdrawRootHash_24 : BitVec 8
  f_withdrawRootHash_25 : BitVec 8
  f_withdrawRootHash_26 : BitVec 8
  f_withdrawRootHash_27 : BitVec 8
  f_withdrawRootHash_28 : BitVec 8
  f_withdrawRootHash_29 : BitVec 8
  f_withdrawRootHash_30 : BitVec 8
  f_withdrawRootHash_31 : BitVec 8
  f_parentBatchHash_0 : BitVec 8
  f_parentBatchHash_1 : BitVec 8
  f_parentBatchHash_2 : BitVec 8
  f_parentBatchHash_3 : BitVec 8
  f_parentBatchHash_4 : BitVec 8
  f_parentBatchHash_5 : BitVec 8
  f_parentBatchHash_6 : BitVec 8
  f_parentBatchHash_7 : BitVec 8
  f_parentBatchHash_8 : BitVec 8
  f_parentBatchHash_9 : BitVec 8
  f_parentBatchHash_10 : BitVec 8
  f_parentBatchHash_11 : BitVec 8
  f_parentBatchHash_12 : BitVec 8
  f_parentBatchHash_13 : BitVec 8
  f_parentBatchHash_14 : BitVec 8
  f_parentBatchHash_15 : BitVec 8
  f_parentBatchHash_16 : BitVec 8
  f_parentBatchHash_17 : BitVec 8
  f_parentBatchHash_18 : BitVec 8
  f_parentBatchHash_19 : BitVec 8
  f_parentBatchHash_20 : BitVec 8
  f_parentBatchHash_21 : BitVec 8
  f_parentBatchHash_22 : BitVec 8
  f_parentBatchHash_23 : BitVec 8
  f_parentBatchHash_24 : BitVec 8
  f_parentBatchHash_25 : BitVec 8
  f_parentBatchHash_26 : BitVec 8
  f_parentBatchHash_27 : BitVec 8
  f_parentBatchHash_28 : BitVec 8
  f_parentBatchHash_29 : BitVec 8
  f_parentBatchHash_30 : BitVec 8
  f_parentBatchHash_31 : BitVec 8
  f_lastBlockNumber_0 : BitVec 8
  f_lastBlockNumber_1 : BitVec 8
  f_lastBlockNumber_2 : BitVec 8
  f_lastBlockNumber_3 : BitVec 8
  f_lastBlockNumber_4 : BitVec 8
  f_lastBlockNumber_5 : BitVec 8
  f_lastBlockNumber_6 : BitVec 8
  f_lastBlockNumber_7 : BitVec 8

def cell_nat : Cell → Nat
  | none => 57005
  | some x => x.toNat

def byte_at : Bytes → Nat → Nat
  | [], _ => 57005
  | c :: _, 0 => cell_nat c
  | _ :: t, n + 1 => byte_at t n

def slice (b : Bytes) (off w : Nat) : Bytes :=
  List.take w (List.drop off b)

def sel : Bool → Bytes → Option Bytes
  | true, x => some x
  | false, _ => none

def c_BatchCache_createBatchHeaderWithSequencerSetHash (h : R_BatchHeaderV1) : Bytes :=
  [some 0x02, some h.f_BatchHeaderV0__BatchIndex_0, some h.f_BatchHeaderV0__BatchIndex_1, some h.f_BatchHeaderV0__BatchIndex_2, some h.f_BatchHeaderV0__BatchIndex_3, some h.f_BatchHeaderV0__BatchIndex_4, some h.f_BatchHeaderV0__BatchIndex_5, some h.f_BatchHeaderV0__BatchIndex_6,
   some h.f_BatchHeaderV0__BatchIndex_7, some h.f_BatchHeaderV0__L1MessagePopped_0, some h.f_BatchHeaderV0__L1MessagePopped_1, some h.f_BatchHeaderV0__L1MessagePopped_2, some h.f_BatchHeaderV0__L1MessagePopped_3, some h.f_BatchHeaderV0__L1MessagePopped_4, some h.f_BatchHeaderV0__L1MessagePopped_5, some h.f_BatchHeaderV0__L1MessagePopped_6,
   some h.f_BatchHeaderV0__L1MessagePopped_7, some h.f_BatchHeaderV0__TotalL1MessagePopped_0, some h.f_BatchHeaderV0__TotalL1MessagePopped_1, some h.f_BatchHeaderV0__TotalL1MessagePopped_2, some h.f_BatchHeaderV0__TotalL1MessagePopped_3, some h.f_BatchHeaderV0__TotalL1MessagePopped_4, some h.f_BatchHeaderV0__TotalL1MessagePopped_5, some h.f_BatchHeaderV0__TotalL1MessagePopped_6,
   some h.f_BatchHeaderV0__TotalL1MessagePopped_7, some h.f_BatchHeaderV0__DataHash_0, some h.f_BatchHeaderV0__DataHash_1, some h.f_BatchHeaderV0__DataHash_2, some h.f_BatchHeaderV0__DataHash_3, some h.f_BatchHeaderV0__DataHash_4, some h.f_BatchHeaderV0__DataHash_5, some h.f_BatchHeaderV0__DataHash_6,
   some h.f_BatchHeaderV0__DataHash_7, some h.f_BatchHeaderV0__DataHash_8, some h.f_BatchHeaderV0__DataHash_9, some h.f_BatchHeaderV0__DataHash_10, some h.f_BatchHeaderV0__DataHash_11, some h.f_BatchHeaderV0__DataHash_12, some h.f_BatchHeaderV0__DataHash_13, some h.f_BatchHeaderV0__DataHash_14,
   some h.f_BatchHeaderV0__DataHash_15, some h.f_BatchHeaderV0__DataHash_16, some h.f_BatchHeaderV0__DataHash_17, some h.f_BatchHeaderV0__DataHash_18, some h.f_BatchHeaderV0__DataHash_19, some h.f_BatchHeaderV0__DataHash_20, some h.f_BatchHeaderV0__DataHash_21, some h.f_BatchHeaderV0__DataHash_22,
   some h.f_BatchHeaderV0__DataHash_23, some h.f_BatchHeaderV0__DataHash_24, some h.f_BatchHeaderV0__DataHash_25, some h.f_BatchHeaderV0__DataHash_26, some h.f_BatchHeaderV0__DataHash_27, some h.f_BatchHeaderV0__DataHash_28, some h.f_BatchHeaderV0__DataHash_29, some h.f_BatchHeaderV0__DataHash_30,
   some h.f_BatchHeaderV0__DataHash_31, some h.f_BatchHeaderV0__BlobVersionedHash_0, some h.f_BatchHeaderV0__BlobVersionedHash_1, some h.f_BatchHeaderV0__BlobVersionedHash_2, some h.f_BatchHeaderV0__BlobVersionedHash_3, some h.f_BatchHeaderV0__BlobVersionedHash_4, some h.f_BatchHeaderV0__BlobVersionedHash_5, some h.f_BatchHeaderV0__BlobVersionedHash_6,
   some h.f_BatchHeaderV0__BlobVersionedHash_7, some h.f_BatchHeaderV0__BlobVersionedHash_8, some h.f_BatchHeaderV0__BlobVersionedHash_9, some h.f_BatchHeaderV0__BlobVersionedHash_10, some h.f_BatchHeaderV0__BlobVersionedHash_11, some h.f_BatchHeaderV0__BlobVersionedHash_12, some h.f_BatchHeaderV0__BlobVersionedHash_13, some h.f_BatchHeaderV0__BlobVersionedHash_14,
   some h.f_BatchHeaderV0__BlobVersionedHash_15, some h.f_BatchHeaderV0__BlobVersionedHash_16, some h.f_BatchHeaderV0__BlobVersionedHash_17, some h.f_BatchHeaderV0__BlobVersionedHash_18, some h.f_BatchHeaderV0__BlobVersionedHash_19, some h.f_BatchHeaderV0__BlobVersionedHash_20, some h.f_BatchHeaderV0__BlobVersionedHash_21, some h.f_BatchHeaderV0__BlobVersionedHash_22,
   some h.f_BatchHeaderV0__BlobVersionedHash_23, some h.f_BatchHeaderV0__BlobVersionedHash_24, some h.f_BatchHeaderV0__BlobVersionedHash_25, some h.f_BatchHeaderV0__BlobVersionedHash_26, some h.f_BatchHeaderV0__BlobVersionedHash_27, some h.f_BatchHeaderV0__BlobVersionedHash_28, some h.f_BatchHeaderV0__BlobVersionedHash_29, some h.f_BatchHeaderV0__BlobVersionedHash_30,
   some h.f_BatchHeaderV0__BlobVersionedHash_31, some h.f_BatchHeaderV0__PrevStateRoot_0, some h.f_BatchHeaderV0__PrevStateRoot_1, some h.f_BatchHeaderV0__PrevStateRoot_2, some h.f_BatchHeaderV0__PrevStateRoot_3, some h.f_BatchHeaderV0__PrevStateRoot_4, some h.f_BatchHeaderV0__PrevStateRoot_5, some h.f_BatchHeaderV0__PrevStateRoot_6,
   some h.f_BatchHeaderV0__PrevStateRoot_7, some h.f_BatchHeaderV0__PrevStateRoot_8, some h.f_BatchHeaderV0__PrevStateRoot_9, some h.f_BatchHeaderV0__PrevStateRoot_10, some h.f_BatchHeaderV0__PrevStateRoot_11, some h.f_BatchHeaderV0__PrevStateRoot_12, some h.f_BatchHeaderV0__PrevStateRoot_13, some h.f_BatchHeaderV0__PrevStateRoot_14,
   some h.f_BatchHeaderV0__PrevStateRoot_15, some h.f_BatchHeaderV0__PrevStateRoot_16, some h.f_BatchHeaderV0__PrevStateRoot_17, some h.f_BatchHeaderV0__PrevStateRoot_18, some h.f_BatchHeaderV0__PrevStateRoot_19, some h.f_BatchHeaderV0__PrevStateRoot_20, some h.f_BatchHeaderV0__PrevStateRoot_21, some h.f_BatchHeaderV0__PrevStateRoot_22,
   some h.f_BatchHeaderV0__PrevStateRoot_23, some h.f_BatchHeaderV0__PrevStateRoot_24, some h.f_BatchHeaderV0__PrevStateRoot_25, some h.f_BatchHeaderV0__PrevStateRoot_26, some h.f_BatchHeaderV0__PrevStateRoot_27, some h.f_BatchHeaderV0__PrevStateRoot_28, some h.f_BatchHeaderV0__PrevStateRoot_29, some h.f_BatchHeaderV0__PrevStateRoot_30,
   some h.f_BatchHeaderV0__PrevStateRoot_31, some h.f_BatchHeaderV0__PostStateRoot_0, some h.f_BatchHeaderV0__PostStateRoot_1, some h.f_BatchHeaderV0__PostStateRoot_2, some h.f_BatchHeaderV0__PostStateRoot_3, some h.f_BatchHeaderV0__PostStateRoot_4, some h.f_BatchHeaderV0__PostStateRoot_5, some h.f_BatchHeaderV0__PostStateRoot_6,
   some h.f_BatchHeaderV0__PostStateRoot_7, some h.f_BatchHeaderV0__PostStateRoot_8, some h.f_BatchHeaderV0__PostStateRoot_9, some h.f_BatchHeaderV0__PostStateRoot_10, some h.f_BatchHeaderV0__PostStateRoot_11, some h.f_BatchHeaderV0__PostStateRoot_12, some h.f_BatchHeaderV0__PostStateRoot_13, some h.f_BatchHeaderV0__PostStateRoot_14,
   some h.f_BatchHeaderV0__PostStateRoot_15, some h.f_BatchHeaderV0__PostStateRoot_16, some h.f_BatchHeaderV0__PostStateRoot_17, some h.f_BatchHeaderV0__PostStateRoot_18, some h.f_BatchHeaderV0__PostStateRoot_19, some h.f_BatchHeaderV0__PostStateRoot_20, some h.f_BatchHeaderV0__PostStateRoot_21, some h.f_BatchHeaderV0__PostStateRoot_22,
   some h.f_BatchHeaderV0__PostStateRoot_23, some h.f_BatchHeaderV0__PostStateRoot_24, some h.f_BatchHeaderV0__PostStateRoot_25, some h.f_BatchHeaderV0__PostStateRoot_26, some h.f_BatchHeaderV0__PostStateRoot_27, some h.f_BatchHeaderV0__PostStateRoot_28, some h.f_BatchHeaderV0__PostStateRoot_29, some h.f_BatchHeaderV0__PostStateRoot_30,
   some h.f_BatchHeaderV0__PostStateRoot_31, some h.f_BatchHeaderV0__WithdrawalRoot_0, some h.f_BatchHeaderV0__WithdrawalRoot_1, some h.f_BatchHeaderV0__WithdrawalRoot_2, some h.f_BatchHeaderV0__WithdrawalRoot_3, some h.f_BatchHeaderV0__WithdrawalRoot_4, some h.f_BatchHeaderV0__WithdrawalRoot_5, some h.f_BatchHeaderV0__WithdrawalRoot_6,
   some h.f_BatchHeaderV0__WithdrawalRoot_7, some h.f_BatchHeaderV0__WithdrawalRoot_8, some h.f_BatchHeaderV0__WithdrawalRoot_9, some h.f_BatchHeaderV0__WithdrawalRoot_10, some h.f_BatchHeaderV0__WithdrawalRoot_11, some h.f_BatchHeaderV0__WithdrawalRoot_12, some h.f_BatchHeaderV0__WithdrawalRoot_13, some h.f_BatchHeaderV0__WithdrawalRoot_14,
   some h.f_BatchHeaderV0__WithdrawalRoot_15, some h.f_BatchHeaderV0__WithdrawalRoot_16, some h.f_BatchHeaderV0__WithdrawalRoot_17, some h.f_BatchHeaderV0__WithdrawalRoot_18, some h.f_BatchHeaderV0__WithdrawalRoot_19, some h.f_BatchHeaderV0__WithdrawalRoot_20, some h.f_BatchHeaderV0__WithdrawalRoot_21, some h.f_BatchHeaderV0__WithdrawalRoot_22,
   some h.f_BatchHeaderV0__WithdrawalRoot_23, some h.f_BatchHeaderV0__WithdrawalRoot_24, some h.f_BatchHeaderV0__WithdrawalRoot_25, some h.f_BatchHeaderV0__WithdrawalRoot_26, some h.f_BatchHeaderV0__WithdrawalRoot_27, some h.f_BatchHeaderV0__WithdrawalRoot_28, some h.f_BatchHeaderV0__WithdrawalRoot_29, some h.f_BatchHeaderV0__WithdrawalRoot_30,
   some h.f_BatchHeaderV0__WithdrawalRoot_31, some h.f_BatchHeaderV0__SequencerSetVerifyHash_0, some h.f_BatchHeaderV0__SequencerSetVerifyHash_1, some h.f_BatchHeaderV0__SequencerSetVerifyHash_2, some h.f_BatchHeaderV0__SequencerSetVerifyHash_3, some h.f_BatchHeaderV0__SequencerSetVerifyHash_4, some h.f_BatchHeaderV0__SequencerSetVerifyHash_5, some h.f_BatchHeaderV0__SequencerSetVerifyHash_6,
   some h.f_BatchHeaderV0__SequencerSetVerifyHash_7, some h.f_BatchHeaderV0__SequencerSetVerifyHash_8, some h.f_BatchHeaderV0__SequencerSetVerifyHash_9, some h.f_BatchHeaderV0__SequencerSetVerifyHash_10, some h.f_BatchHeaderV0__SequencerSetVerifyHash_11, some h.f_BatchHeaderV0__SequencerSetVerifyHash_12, some h.f_BatchHeaderV0__SequencerSetVerifyHash_13, some h.f_BatchHeaderV0__SequencerSetVerifyHash_14,
   some h.f_BatchHeaderV0__SequencerSetVerifyHash_15, some h.f_BatchHeaderV0__SequencerSetVerifyHash_16, some h.f_BatchHeaderV0__SequencerSetVerifyHash_17, some h.f_BatchHeaderV0__SequencerSetVerifyHash_18, some h.f_BatchHeaderV0__SequencerSetVerifyHash_19, some h.f_BatchHeaderV0__SequencerSetVerifyHash_20, some h.f_BatchHeaderV0__SequencerSetVerifyHash_21, some h.f_BatchHeaderV0__SequencerSetVerifyHash_22,
   some h.f_BatchHeaderV0__SequencerSetVerifyHash_23, some h.f_BatchHeaderV0__SequencerSetVerifyHash_24, some h.f_BatchHeaderV0__SequencerSetVerifyHash_25, some h.f_BatchHeaderV0__SequencerSetVerifyHash_26, some h.f_BatchHeaderV0__SequencerSetVerifyHash_27, some h.f_BatchHeaderV0__SequencerSetVerifyHash_28, some h.f_BatchHeaderV0__SequencerSetVerifyHash_29, some h.f_BatchHeaderV0__SequencerSetVerifyHash_30,
   some h.f_BatchHeaderV0__SequencerSetVerifyHash_31, some h.f_BatchHeaderV0__ParentBatchHash_0, some h.f_BatchHeaderV0__ParentBatchHash_1, some h.f_BatchHeaderV0__ParentBatchHash_2, some h.f_BatchHeaderV0__ParentBatchHash_3, some h.f_BatchHeaderV0__ParentBatchHash_4, some h.f_BatchHeaderV0__ParentBatchHash_5, some h.f_BatchHeaderV0__ParentBatchHash_6,
   some h.f_BatchHeaderV0__ParentBatchHash_7, some h.f_BatchHeaderV0__ParentBatchHash_8, some h.f_BatchHeaderV0__ParentBatchHash_9, some h.f_BatchHeaderV0__ParentBatchHash_10, some h.f_BatchHeaderV0__ParentBatchHash_11, some h.f_BatchHeaderV0__ParentBatchHash_12, some h.f_BatchHeaderV0__ParentBatchHash_13, some h.f_BatchHeaderV0__ParentBatchHash_14,
   some h.f_BatchHeaderV0__ParentBatchHash_15, some h.f_BatchHeaderV0__ParentBatchHash_16, some h.f_BatchHeaderV0__ParentBatchHash_17, some h.f_BatchHeaderV0__ParentBatchHash_18, some h.f_BatchHeaderV0__ParentBatchHash_19, some h.f_BatchHeaderV0__ParentBatchHash_20, some h.f_BatchHeaderV0__ParentBatchHash_21, some h.f_BatchHeaderV0__ParentBatchHash_22,
   some h.f_BatchHeaderV0__ParentBatchHash_23, some h.f_BatchHeaderV0__ParentBatchHash_24, some h.f_BatchHeaderV0__ParentBatchHash_25, some h.f_BatchHeaderV0__ParentBatchHash_26, some h.f_BatchHeaderV0__ParentBatchHash_27, some h.f_BatchHeaderV0__ParentBatchHash_28, some h.f_BatchHeaderV0__ParentBatchHash_29, some h.f_BatchHeaderV0__ParentBatchHash_30,
   some h.f_BatchHeaderV0__ParentBatchHash_31, some h.f_LastBlockNumber_0, some h.f_LastBlockNumber_1, some h.f_LastBlockNumber_2, some h.f_LastBlockNumber_3, some h.f_LastBlockNumber_4, some h.f_LastBlockNumber_5, some h.f_LastBlockNumber_6,
   some h.f_LastBlockNumber_7]

def c_ok_BatchHeaderBytes_BatchIndex (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_BatchIndex (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_BatchIndex b) (slice b 1 8)

def c_ok_BatchHeaderBytes_BlobCommitHash (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.ble 2 (byte_at b 0)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (Nat.blt (byte_at b 0) 2) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (Nat.blt (byte_at b 0) 2) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_BlobCommitHash (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_BlobCommitHash b) (slice b 57 32)

def c_ok_BatchHeaderBytes_BlobHashesHash (b : Bytes) : Bool :=
  ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257))

def c_BatchHeaderBytes_BlobHashesHash (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_BlobHashesHash b) (slice b 57 32)

def c_ok_BatchHeaderBytes_BlobVersionedHash (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_BlobVersionedHash (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_BlobVersionedHash b) (slice b 57 32)

def c_ok_BatchHeaderBytes_DataHash (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_DataHash (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_DataHash b) (slice b 25 32)

def c_ok_BatchHeaderBytes_L1MessagePopped (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_L1MessagePopped (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_L1MessagePopped b) (slice b 9 8)

def c_ok_BatchHeaderBytes_LastBlockNumber (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_LastBlockNumber (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_LastBlockNumber b) (slice b 249 8)

def c_ok_BatchHeaderBytes_ParentBatchHash (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_ParentBatchHash (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_ParentBatchHash b) (slice b 217 32)

def c_ok_BatchHeaderBytes_PostStateRoot (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_PostStateRoot (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_PostStateRoot b) (slice b 121 32)

def c_ok_BatchHeaderBytes_PrevStateRoot (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_PrevStateRoot (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_PrevStateRoot b) (slice b 89 32)

def c_ok_BatchHeaderBytes_SequencerSetVerifyHash (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_SequencerSetVerifyHash (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_SequencerSetVerifyHash b) (slice b 185 32)

def c_ok_BatchHeaderBytes_TotalL1MessagePopped (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_TotalL1MessagePopped (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_TotalL1MessagePopped b) (slice b 17 8)

def c_ok_BatchHeaderBytes_Version (b : Bytes) : Bool :=
  (!(Nat.beq (List.length b) 0))

def c_BatchHeaderBytes_Version (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_Version b) (slice b 0 1)

def c_ok_BatchHeaderBytes_WithdrawalRoot (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderBytes_WithdrawalRoot (b : Bytes) : Option Bytes :=
  sel (c_ok_BatchHeaderBytes_WithdrawalRoot b) (slice b 153 32)

def c_BatchHeaderBytes_validate (b : Bytes) : Bool :=
  (((!(Nat.beq (List.length b) 0)) && (Nat.beq (byte_at b 0) 0) && (Nat.beq (List.length b) 249)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (Nat.beq (byte_at b 0) 1) && (Nat.beq (List.length b) 257)) ||
    ((!(Nat.beq (List.length b) 0)) && (!(Nat.beq (byte_at b 0) 0)) && (!(Nat.beq (byte_at b 0) 1)) && (Nat.beq (byte_at b 0) 2) && (Nat.beq (List.length b) 257)))

def c_BatchHeaderV0_Bytes (h : R_BatchHeaderV0) : Bytes :=
  [some 0x00, some h.f_BatchIndex_0, some h.f_BatchIndex_1, some h.f_BatchIndex_2, some h.f_BatchIndex_3, some h.f_BatchIndex_4, some h.f_BatchIndex_5, some h.f_BatchIndex_6,
   some h.f_BatchIndex_7, some h.f_L1MessagePopped_0, some h.f_L1MessagePopped_1, some h.f_L1MessagePopped_2, some h.f_L1MessagePopped_3, some h.f_L1MessagePopped_4, some h.f_L1MessagePopped_5, some h.f_L1MessagePopped_6,
   some h.f_L1MessagePopped_7, some h.f_TotalL1MessagePopped_0, some h.f_TotalL1MessagePopped_1, some h.f_TotalL1MessagePopped_2, some h.f_TotalL1MessagePopped_3, some h.f_TotalL1MessagePopped_4, some h.f_TotalL1MessagePopped_5, some h.f_TotalL1MessagePopped_6,
   some h.f_TotalL1MessagePopped_7, some h.f_DataHash_0, some h.f_DataHash_1, some h.f_DataHash_2, some h.f_DataHash_3, some h.f_DataHash_4, some h.f_DataHash_5, some h.f_DataHash_6,
   some h.f_DataHash_7, some h.f_DataHash_8, some h.f_DataHash_9, some h.f_DataHash_10, some h.f_DataHash_11, some h.f_DataHash_12, some h.f_DataHash_13, some h.f_DataHash_14,
   some h.f_DataHash_15, some h.f_DataHash_16, some h.f_DataHash_17, some h.f_DataHash_18, some h.f_DataHash_19, some h.f_DataHash_20, some h.f_DataHash_21, some h.f_DataHash_22,
   some h.f_DataHash_23, some h.f_DataHash_24, some h.f_DataHash_25, some h.f_DataHash_26, some h.f_DataHash_27, some h.f_DataHash_28, some h.f_DataHash_29, some h.f_DataHash_30,
   some h.f_DataHash_31, some h.f_BlobVersionedHash_0, some h.f_BlobVersionedHash_1, some h.f_BlobVersionedHash_2, some h.f_BlobVersionedHash_3, some h.f_BlobVersionedHash_4, some h.f_BlobVersionedHash_5, some h.f_BlobVersionedHash_6,
   some h.f_BlobVersionedHash_7, some h.f_BlobVersionedHash_8, some h.f_BlobVersionedHash_9, some h.f_BlobVersionedHash_10, some h.f_BlobVersionedHash_11, some h.f_BlobVersionedHash_12, some h.f_BlobVersionedHash_13, some h.f_BlobVersionedHash_14,
   some h.f_BlobVersionedHash_15, some h.f_BlobVersionedHash_16, some h.f_BlobVersionedHash_17, some h.f_BlobVersionedHash_18, some h.f_BlobVersionedHash_19, some h.f_BlobVersionedHash_20, some h.f_BlobVersionedHash_21, some h.f_BlobVersionedHash_22,
   some h.f_BlobVersionedHash_23, some h.f_BlobVersionedHash_24, some h.f_BlobVersionedHash_25, some h.f_BlobVersionedHash_26, some h.f_BlobVersionedHash_27, some h.f_BlobVersionedHash_28, some h.f_BlobVersionedHash_29, some h.f_BlobVersionedHash_30,
   some h.f_BlobVersionedHash_31, some h.f_PrevStateRoot_0, some h.f_PrevStateRoot_1, some h.f_PrevStateRoot_2, some h.f_PrevStateRoot_3, some h.f_PrevStateRoot_4, some h.f_PrevStateRoot_5, some h.f_PrevStateRoot_6,
   some h.f_PrevStateRoot_7, some h.f_PrevStateRoot_8, some h.f_PrevStateRoot_9, some h.f_PrevStateRoot_10, some h.f_PrevStateRoot_11, some h.f_PrevStateRoot_12, some h.f_PrevStateRoot_13, some h.f_PrevStateRoot_14,
   some h.f_PrevStateRoot_15, some h.f_PrevStateRoot_16, some h.f_PrevStateRoot_17, some h.f_PrevStateRoot_18, some h.f_PrevStateRoot_19, some h.f_PrevStateRoot_20, some h.f_PrevStateRoot_21, some h.f_PrevStateRoot_22,
   some h.f_PrevStateRoot_23, some h.f_PrevStateRoot_24, some h.f_PrevStateRoot_25, some h.f_PrevStateRoot_26, some h.f_PrevStateRoot_27, some h.f_PrevStateRoot_28, some h.f_PrevStateRoot_29, some h.f_PrevStateRoot_30,
   some h.f_PrevStateRoot_31, some h.f_PostStateRoot_0, some h.f_PostStateRoot_1, some h.f_PostStateRoot_2, some h.f_PostStateRoot_3, some h.f_PostStateRoot_4, some h.f_PostStateRoot_5, some h.f_PostStateRoot_6,
   some h.f_PostStateRoot_7, some h.f_PostStateRoot_8, some h.f_PostStateRoot_9, some h.f_PostStateRoot_10, some h.f_PostStateRoot_11, some h.f_PostStateRoot_12, some h.f_PostStateRoot_13, some h.f_PostStateRoot_14,
   some h.f_PostStateRoot_15, some h.f_PostStateRoot_16, some h.f_PostStateRoot_17, some h.f_PostStateRoot_18, some h.f_PostStateRoot_19, some h.f_PostStateRoot_20, some h.f_PostStateRoot_21, some h.f_PostStateRoot_22,
   some h.f_PostStateRoot_23, some h.f_PostStateRoot_24, some h.f_PostStateRoot_25, some h.f_PostStateRoot_26, some h.f_PostStateRoot_27, some h.f_PostStateRoot_28, some h.f_PostStateRoot_29, some h.f_PostStateRoot_30,
   some h.f_PostStateRoot_31, some h.f_WithdrawalRoot_0, some h.f_WithdrawalRoot_1, some h.f_WithdrawalRoot_2, some h.f_WithdrawalRoot_3, some h.f_WithdrawalRoot_4, some h.f_WithdrawalRoot_5, some h.f_WithdrawalRoot_6,
   some h.f_WithdrawalRoot_7, some h.f_WithdrawalRoot_8, some h.f_WithdrawalRoot_9, some h.f_WithdrawalRoot_10, some h.f_WithdrawalRoot_11, some h.f_WithdrawalRoot_12, some h.f_WithdrawalRoot_13, some h.f_WithdrawalRoot_14,
   some h.f_WithdrawalRoot_15, some h.f_WithdrawalRoot_16, some h.f_WithdrawalRoot_17, some h.f_WithdrawalRoot_18, some h.f_WithdrawalRoot_19, some h.f_WithdrawalRoot_20, some h.f_WithdrawalRoot_21, some h.f_WithdrawalRoot_22,
   some h.f_WithdrawalRoot_23, some h.f_WithdrawalRoot_24, some h.f_WithdrawalRoot_25, some h.f_WithdrawalRoot_26, some h.f_WithdrawalRoot_27, some h.f_WithdrawalRoot_28, some h.f_WithdrawalRoot_29, some h.f_WithdrawalRoot_30,
   some h.f_WithdrawalRoot_31, some h.f_SequencerSetVerifyHash_0, some h.f_SequencerSetVerifyHash_1, some h.f_SequencerSetVerifyHash_2, some h.f_SequencerSetVerifyHash_3, some h.f_SequencerSetVerifyHash_4, some h.f_SequencerSetVerifyHash_5, some h.f_SequencerSetVerifyHash_6,
   some h.f_SequencerSetVerifyHash_7, some h.f_SequencerSetVerifyHash_8, some h.f_SequencerSetVerifyHash_9, some h.f_SequencerSetVerifyHash_10, some h.f_SequencerSetVerifyHash_11, some h.f_SequencerSetVerifyHash_12, some h.f_SequencerSetVerifyHash_13, some h.f_SequencerSetVerifyHash_14,
   some h.f_SequencerSetVerifyHash_15, some h.f_SequencerSetVerifyHash_16, some h.f_SequencerSetVerifyHash_17, some h.f_SequencerSetVerifyHash_18, some h.f_SequencerSetVerifyHash_19, some h.f_SequencerSetVerifyHash_20, some h.f_SequencerSetVerifyHash_21, some h.f_SequencerSetVerifyHash_22,
   some h.f_SequencerSetVerifyHash_23, some h.f_SequencerSetVerifyHash_24, some h.f_SequencerSetVerifyHash_25, some h.f_SequencerSetVerifyHash_26, some h.f_SequencerSetVerifyHash_27, some h.f_SequencerSetVerifyHash_28, some h.f_SequencerSetVerifyHash_29, some h.f_SequencerSetVerifyHash_30,
   some h.f_SequencerSetVerifyHash_31, some h.f_ParentBatchHash_0, some h.f_ParentBatchHash_1, some h.f_ParentBatchHash_2, some h.f_ParentBatchHash_3, some h.f_ParentBatchHash_4, some h.f_ParentBatchHash_5, some h.f_ParentBatchHash_6,
   some h.f_ParentBatchHash_7, some h.f_ParentBatchHash_8, some h.f_ParentBatchHash_9, some h.f_ParentBatchHash_10, some h.f_ParentBatchHash_11, some h.f_ParentBatchHash_12, some h.f_ParentBatchHash_13, some h.f_ParentBatchHash_14,
   some h.f_ParentBatchHash_15, some h.f_ParentBatchHash_16, some h.f_ParentBatchHash_17, some h.f_ParentBatchHash_18, some h.f_ParentBatchHash_19, some h.f_ParentBatchHash_20, some h.f_ParentBatchHash_21, some h.f_ParentBatchHash_22,
   some h.f_ParentBatchHash_23, some h.f_ParentBatchHash_24, some h.f_ParentBatchHash_25, some h.f_ParentBatchHash_26, some h.f_ParentBatchHash_27, some h.f_ParentBatchHash_28, some h.f_ParentBatchHash_29, some h.f_ParentBatchHash_30,
   some h.f_ParentBatchHash_31]

def c_BatchHeaderV1_Bytes (h : R_BatchHeaderV1) : Bytes :=
  [some 0x01, some h.f_BatchHeaderV0__BatchIndex_0, some h.f_BatchHeaderV0__BatchIndex_1, some h.f_BatchHeaderV0__BatchIndex_2, some h.f_BatchHeaderV0__BatchIndex_3, some h.f_BatchHeaderV0__BatchIndex_4, some h.f_BatchHeaderV0__BatchIndex_5, some h.f_BatchHeaderV0__BatchIndex_6,
   some h.f_BatchHeaderV0__BatchIndex_7, some h.f_BatchHeaderV0__L1MessagePopped_0, some h.f_BatchHeaderV0__L1MessagePopped_1, some h.f_BatchHeaderV0__L1MessagePopped_2, some h.f_BatchHeaderV0__L1MessagePopped_3, some h.f_BatchHeaderV0__L1MessagePopped_4, some h.f_BatchHeaderV0__L1MessagePopped_5, some h.f_BatchHeaderV0__L1MessagePopped_6,
   some h.f_BatchHeaderV0__L1MessagePopped_7, some h.f_BatchHeaderV0__TotalL1MessagePopped_0, some h.f_BatchHeaderV0__TotalL1MessagePopped_1, some h.f_BatchHeaderV0__TotalL1MessagePopped_2, some h.f_BatchHeaderV0__TotalL1MessagePopped_3, some h.f_BatchHeaderV0__TotalL1MessagePopped_4, some h.f_BatchHeaderV0__TotalL1MessagePopped_5, some h.f_BatchHeaderV0__TotalL1MessagePopped_6,
   some h.f_BatchHeaderV0__TotalL1MessagePopped_7, some h.f_BatchHeaderV0__DataHash_0, some h.f_BatchHeaderV0__DataHash_1, some h.f_BatchHeaderV0__DataHash_2, some h.f_BatchHeaderV0__DataHash_3, some h.f_BatchHeaderV0__DataHash_4, some h.f_BatchHeaderV0__DataHash_5, some h.f_BatchHeaderV0__DataHash_6,
   some h.f_BatchHeaderV0__DataHash_7, some h.f_BatchHeaderV0__DataHash_8, some h.f_BatchHeaderV0__DataHash_9, some h.f_BatchHeaderV0__DataHash_10, some h.f_BatchHeaderV0__DataHash_11, some h.f_BatchHeaderV0__DataHash_12, some h.f_BatchHeaderV0__DataHash_13, some h.f_BatchHeaderV0__DataHash_14,
   some h.f_BatchHeaderV0__DataHash_15, some h.f_BatchHeaderV0__DataHash_16, some h.f_BatchHeaderV0__DataHash_17, some h.f_BatchHeaderV0__DataHash_18, some h.f_BatchHeaderV0__DataHash_19, some h.f_BatchHeaderV0__DataHash_20, some h.f_BatchHeaderV0__DataHash_21, some h.f_BatchHeaderV0__DataHash_22,
   some h.f_BatchHeaderV0__DataHash_23, some h.f_BatchHeaderV0__DataHash_24, some h.f_BatchHeaderV0__DataHash_25, some h.f_BatchHeaderV0__DataHash_26, some h.f_BatchHeaderV0__DataHash_27, some h.f_BatchHeaderV0__DataHash_28, some h.f_BatchHeaderV0__DataHash_29, some h.f_BatchHeaderV0__DataHash_30,
   some h.f_BatchHeaderV0__DataHash_31, some h.f_BatchHeaderV0__BlobVersionedHash_0, some h.f_BatchHeaderV0__BlobVersionedHash_1, some h.f_BatchHeaderV0__BlobVersionedHash_2, some h.f_BatchHeaderV0__BlobVersionedHash_3, some h.f_BatchHeaderV0__BlobVersionedHash_4, some h.f_BatchHeaderV0__BlobVersionedHash_5, some h.f_BatchHeaderV0__BlobVersionedHash_6,
   some h.f_BatchHeaderV0__BlobVersionedHash_7, some h.f_BatchHeaderV0__BlobVersionedHash_8, some h.f_BatchHeaderV0__BlobVersionedHash_9, some h.f_BatchHeaderV0__BlobVersionedHash_10, some h.f_BatchHeaderV0__BlobVersionedHash_11, some h.f_BatchHeaderV0__BlobVersionedHash_12, some h.f_BatchHeaderV0__BlobVersionedHash_13, some h.f_BatchHeaderV0__BlobVersionedHash_14,
   some h.f_BatchHeaderV0__BlobVersionedHash_15, some h.f_BatchHeaderV0__BlobVersionedHash_16, some h.f_BatchHeaderV0__BlobVersionedHash_17, some h.f_BatchHeaderV0__BlobVersionedHash_18, some h.f_BatchHeaderV0__BlobVersionedHash_19, some h.f_BatchHeaderV0__BlobVersionedHash_20, some h.f_BatchHeaderV0__BlobVersionedHash_21, some h.f_BatchHeaderV0__BlobVersionedHash_22,
   some h.f_BatchHeaderV0__BlobVersionedHash_23, some h.f_BatchHeaderV0__BlobVersionedHash_24, some h.f_BatchHeaderV0__BlobVersionedHash_25, some h.f_BatchHeaderV0__BlobVersionedHash_26, some h.f_BatchHeaderV0__BlobVersionedHash_27, some h.f_BatchHeaderV0__BlobVersionedHash_28, some h.f_BatchHeaderV0__BlobVersionedHash_29, some h.f_BatchHeaderV0__BlobVersionedHash_30,
   some h.f_BatchHeaderV0__BlobVersionedHash_31, some h.f_BatchHeaderV0__PrevStateRoot_0, some h.f_BatchHeaderV0__PrevStateRoot_1, some h.f_BatchHeaderV0__PrevStateRoot_2, some h.f_BatchHeaderV0__PrevStateRoot_3, some h.f_BatchHeaderV0__PrevStateRoot_4, some h.f_BatchHeaderV0__PrevStateRoot_5, some h.f_BatchHeaderV0__PrevStateRoot_6,
   some h.f_BatchHeaderV0__PrevStateRoot_7, some h.f_BatchHeaderV0__PrevStateRoot_8, some h.f_BatchHeaderV0__PrevStateRoot_9, some h.f_BatchHeaderV0__PrevStateRoot_10, some h.f_BatchHeaderV0__PrevStateRoot_11, some h.f_BatchHeaderV0__PrevStateRoot_12, some h.f_BatchHeaderV0__PrevStateRoot_13, some h.f_BatchHeaderV0__PrevStateRoot_14,
   some h.f_BatchHeaderV0__PrevStateRoot_15, some h.f_BatchHeaderV0__PrevStateRoot_16, some h.f_BatchHeaderV0__PrevStateRoot_17, some h.f_BatchHeaderV0__PrevStateRoot_18, some h.f_BatchHeaderV0__PrevStateRoot_19, some h.f_BatchHeaderV0__PrevStateRoot_20, some h.f_BatchHeaderV0__PrevStateRoot_21, some h.f_BatchHeaderV0__PrevStateRoot_22,
   some h.f_BatchHeaderV0__PrevStateRoot_23, some h.f_BatchHeaderV0__PrevStateRoot_24, some h.f_BatchHeaderV0__PrevStateRoot_25, some h.f_BatchHeaderV0__PrevStateRoot_26, some h.f_BatchHeaderV0__PrevStateRoot_27, some h.f_BatchHeaderV0__PrevStateRoot_28, some h.f_BatchHeaderV0__PrevStateRoot_29, some h.f_BatchHeaderV0__PrevStateRoot_30,
   some h.f_BatchHeaderV0__PrevStateRoot_31, some h.f_BatchHeaderV0__PostStateRoot_0, some h.f_BatchHeaderV0__PostStateRoot_1, some h.f_BatchHeaderV0__PostStateRoot_2, some h.f_BatchHeaderV0__PostStateRoot_3, some h.f_BatchHeaderV0__PostStateRoot_4, some h.f_BatchHeaderV0__PostStateRoot_5, some h.f_BatchHeaderV0__PostStateRoot_6,
   some h.f_BatchHeaderV0__PostStateRoot_7, some h.f_BatchHeaderV0__PostStateRoot_8, some h.f_BatchHeaderV0__PostStateRoot_9, some h.f_BatchHeaderV0__PostStateRoot_10, some h.f_BatchHeaderV0__PostStateRoot_11, some h.f_BatchHeaderV0__PostStateRoot_12, some h.f_BatchHeaderV0__PostStateRoot_13, some h.f_BatchHeaderV0__PostStateRoot_14,
   some h.f_BatchHeaderV0__PostStateRoot_15, some h.f_BatchHeaderV0__PostStateRoot_16, some h.f_BatchHeaderV0__PostStateRoot_17, some h.f_BatchHeaderV0__PostStateRoot_18, some h.f_BatchHeaderV0__PostStateRoot_19, some h.f_BatchHeaderV0__PostStateRoot_20, some h.f_BatchHeaderV0__PostStateRoot_21, some h.f_BatchHeaderV0__PostStateRoot_22,
   some h.f_BatchHeaderV0__PostStateRoot_23, some h.f_BatchHeaderV0__PostStateRoot_24, some h.f_BatchHeaderV0__PostStateRoot_25, some h.f_BatchHeaderV0__PostStateRoot_26, some h.f_BatchHeaderV0__PostStateRoot_27, some h.f_BatchHeaderV0__PostStateRoot_28, some h.f_BatchHeaderV0__PostStateRoot_29, some h.f_BatchHeaderV0__PostStateRoot_30,
   some h.f_BatchHeaderV0__PostStateRoot_31, some h.f_BatchHeaderV0__WithdrawalRoot_0, some h.f_BatchHeaderV0__WithdrawalRoot_1, some h.f_BatchHeaderV0__WithdrawalRoot_2, some h.f_BatchHeaderV0__WithdrawalRoot_3, some h.f_BatchHeaderV0__WithdrawalRoot_4, some h.f_BatchHeaderV0__WithdrawalRoot_5, some h.f_BatchHeaderV0__WithdrawalRoot_6,
   some h.f_BatchHeaderV0__WithdrawalRoot_7, some h.f_BatchHeaderV0__WithdrawalRoot_8, some h.f_BatchHeaderV0__WithdrawalRoot_9, some h.f_BatchHeaderV0__WithdrawalRoot_10, some h.f_BatchHeaderV0__WithdrawalRoot_11, some h.f_BatchHeaderV0__WithdrawalRoot_12, some h.f_BatchHeaderV0__WithdrawalRoot_13, some h.f_BatchHeaderV0__WithdrawalRoot_14,
   some h.f_BatchHeaderV0__WithdrawalRoot_15, some h.f_BatchHeaderV0__WithdrawalRoot_16, some h.f_BatchHeaderV0__WithdrawalRoot_17, some h.f_BatchHeaderV0__WithdrawalRoot_18, some h.f_BatchHeaderV0__WithdrawalRoot_19, some h.f_BatchHeaderV0__WithdrawalRoot_20, some h.f_BatchHeaderV0__WithdrawalRoot_21, some h.f_BatchHeaderV0__WithdrawalRoot_22,
   some h.f_BatchHeaderV0__WithdrawalRoot_23, some h.f_BatchHeaderV0__WithdrawalRoot_24, some h.f_BatchHeaderV0__WithdrawalRoot_25, some h.f_BatchHeaderV0__WithdrawalRoot_26, some h.f_BatchHeaderV0__WithdrawalRoot_27, some h.f_BatchHeaderV0__WithdrawalRoot_28, some h.f_BatchHeaderV0__WithdrawalRoot_29, some h.f_BatchHeaderV0__WithdrawalRoot_30,
   some h.f_BatchHeaderV0__WithdrawalRoot_31, some h.f_BatchHeaderV0__SequencerSetVerifyHash_0, some h.f_BatchHeaderV0__SequencerSetVerifyHash_1, some h.f_BatchHeaderV0__SequencerSetVerifyHash_2, some h.f_BatchHeaderV0__SequencerSetVerifyHash_3, some h.f_BatchHeaderV0__SequencerSetVerifyHash_4, some h.f_BatchHeaderV0__SequencerSetVerifyHash_5, some h.f_BatchHeaderV0__SequencerSetVerifyHash_6,
   some h.f_BatchHeaderV0__SequencerSetVerifyHash_7, some h.f_BatchHeaderV0__SequencerSetVerifyHash_8, some h.f_BatchHeaderV0__SequencerSetVerifyHash_9, some h.f_BatchHeaderV0__SequencerSetVerifyHash_10, some h.f_BatchHeaderV0__SequencerSetVerifyHash_11, some h.f_BatchHeaderV0__SequencerSetVerifyHash_12, some h.f_BatchHeaderV0__SequencerSetVerifyHash_13, some h.f_BatchHeaderV0__SequencerSetVerifyHash_14,
   some h.f_BatchHeaderV0__SequencerSetVerifyHash_15, some h.f_BatchHeaderV0__SequencerSetVerifyHash_16, some h.f_BatchHeaderV0__SequencerSetVerifyHash_17, some h.f_BatchHeaderV0__SequencerSetVerifyHash_18, some h.f_BatchHeaderV0__SequencerSetVerifyHash_19, some h.f_BatchHeaderV0__SequencerSetVerifyHash_20, some h.f_BatchHeaderV0__SequencerSetVerifyHash_21, some h.f_BatchHeaderV0__SequencerSetVerifyHash_22,
   some h.f_BatchHeaderV0__SequencerSetVerifyHash_23, some h.f_BatchHeaderV0__SequencerSetVerifyHash_24, some h.f_BatchHeaderV0__SequencerSetVerifyHash_25, some h.f_BatchHeaderV0__SequencerSetVerifyHash_26, some h.f_BatchHeaderV0__SequencerSetVerifyHash_27, some h.f_BatchHeaderV0__SequencerSetVerifyHash_28, some h.f_BatchHeaderV0__SequencerSetVerifyHash_29, some h.f_BatchHeaderV0__SequencerSetVerifyHash_30,
   some h.f_BatchHeaderV0__SequencerSetVerifyHash_31, some h.f_BatchHeaderV0__ParentBatchHash_0, some h.f_BatchHeaderV0__ParentBatchHash_1, some h.f_BatchHeaderV0__ParentBatchHash_2, some h.f_BatchHeaderV0__ParentBatchHash_3, some h.f_BatchHeaderV0__ParentBatchHash_4, some h.f_BatchHeaderV0__ParentBatchHash_5, some h.f_BatchHeaderV0__ParentBatchHash_6,
   some h.f_BatchHeaderV0__ParentBatchHash_7, some h.f_BatchHeaderV0__ParentBatchHash_8, some h.f_BatchHeaderV0__ParentBatchHash_9, some h.f_BatchHeaderV0__ParentBatchHash_10, some h.f_BatchHeaderV0__ParentBatchHash_11, some h.f_BatchHeaderV0__ParentBatchHash_12, some h.f_BatchHeaderV0__ParentBatchHash_13, some h.f_BatchHeaderV0__ParentBatchHash_14,
   some h.f_BatchHeaderV0__ParentBatchHash_15, some h.f_BatchHeaderV0__ParentBatchHash_16, some h.f_BatchHeaderV0__ParentBatchHash_17, some h.f_BatchHeaderV0__ParentBatchHash_18, some h.f_BatchHeaderV0__ParentBatchHash_19, some h.f_BatchHeaderV0__ParentBatchHash_20, some h.f_BatchHeaderV0__ParentBatchHash_21, some h.f_BatchHeaderV0__ParentBatchHash_22,
   some h.f_BatchHeaderV0__ParentBatchHash_23, some h.f_BatchHeaderV0__ParentBatchHash_24, some h.f_BatchHeaderV0__ParentBatchHash_25, some h.f_BatchHeaderV0__ParentBatchHash_26, some h.f_BatchHeaderV0__ParentBatchHash_27, some h.f_BatchHeaderV0__ParentBatchHash_28, some h.f_BatchHeaderV0__ParentBatchHash_29, some h.f_BatchHeaderV0__ParentBatchHash_30,
   some h.f_BatchHeaderV0__ParentBatchHash_31, some h.f_LastBlockNumber_0, some h.f_LastBlockNumber_1, some h.f_LastBlockNumber_2, some h.f_LastBlockNumber_3, some h.f_LastBlockNumber_4, some h.f_LastBlockNumber_5, some h.f_LastBlockNumber_6,
   some h.f_LastBlockNumber_7]

def c_enc_sol (h : R_Header) : Bytes :=
  match h.f_version_0.toNat with
  | 0 =>
    [some h.f_version_0, some h.f_batchIndex_0, some h.f_batchIndex_1, some h.f_batchIndex_2, some h.f_batchIndex_3, some h.f_batchIndex_4, some h.f_batchIndex_5, some h.f_batchIndex_6,
     some h.f_batchIndex_7, some h.f_l1MessagePopped_0, some h.f_l1MessagePopped_1, some h.f_l1MessagePopped_2, some h.f_l1MessagePopped_3, some h.f_l1MessagePopped_4, some h.f_l1MessagePopped_5, some h.f_l1MessagePopped_6,
     some h.f_l1MessagePopped_7, some h.f_totalL1MessagePopped_0, some h.f_totalL1MessagePopped_1, some h.f_totalL1MessagePopped_2, some h.f_totalL1MessagePopped_3, some h.f_totalL1MessagePopped_4, some h.f_totalL1MessagePopped_5, some h.f_totalL1MessagePopped_6,
     some h.f_totalL1MessagePopped_7, some h.f_dataHash_0, some h.f_dataHash_1, some h.f_dataHash_2, some h.f_dataHash_3, some h.f_dataHash_4, some h.f_dataHash_5, some h.f_dataHash_6,
     some h.f_dataHash_7, some h.f_dataHash_8, some h.f_dataHash_9, some h.f_dataHash_10, some h.f_dataHash_11, some h.f_dataHash_12, some h.f_dataHash_13, some h.f_dataHash_14,
     some h.f_dataHash_15, some h.f_dataHash_16, some h.f_dataHash_17, some h.f_dataHash_18, some h.f_dataHash_19, some h.f_dataHash_20, some h.f_dataHash_21, some h.f_dataHash_22,
     some h.f_dataHash_23, some h.f_dataHash_24, some h.f_dataHash_25, some h.f_dataHash_26, some h.f_dataHash_27, some h.f_dataHash_28, some h.f_dataHash_29, some h.f_dataHash_30,
     some h.f_dataHash_31, some h.f_blobVersionedHash_0, some h.f_blobVersionedHash_1, some h.f_blobVersionedHash_2, some h.f_blobVersionedHash_3, some h.f_blobVersionedHash_4, some h.f_blobVersionedHash_5, some h.f_blobVersionedHash_6,
     some h.f_blobVersionedHash_7, some h.f_blobVersionedHash_8, some h.f_blobVersionedHash_9, some h.f_blobVersionedHash_10, some h.f_blobVersionedHash_11, some h.f_blobVersionedHash_12, some h.f_blobVersionedHash_13, some h.f_blobVersionedHash_14,
     some h.f_blobVersionedHash_15, some h.f_blobVersionedHash_16, some h.f_blobVersionedHash_17, some h.f_blobVersionedHash_18, some h.f_blobVersionedHash_19, some h.f_blobVersionedHash_20, some h.f_blobVersionedHash_21, some h.f_blobVersionedHash_22,
     some h.f_blobVersionedHash_23, some h.f_blobVersionedHash_24, some h.f_blobVersionedHash_25, some h.f_blobVersionedHash_26, some h.f_blobVersionedHash_27, some h.f_blobVersionedHash_28, some h.f_blobVersionedHash_29, some h.f_blobVersionedHash_30,
     some h.f_blobVersionedHash_31, some h.f_prevStateHash_0, some h.f_prevStateHash_1, some h.f_prevStateHash_2, some h.f_prevStateHash_3, some h.f_prevStateHash_4, some h.f_prevStateHash_5, some h.f_prevStateHash_6,
     some h.f_prevStateHash_7, some h.f_prevStateHash_8, some h.f_prevStateHash_9, some h.f_prevStateHash_10, some h.f_prevStateHash_11, some h.f_prevStateHash_12, some h.f_prevStateHash_13, some h.f_prevStateHash_14,
     some h.f_prevStateHash_15, some h.f_prevStateHash_16, some h.f_prevStateHash_17, some h.f_prevStateHash_18, some h.f_prevStateHash_19, some h.f_prevStateHash_20, some h.f_prevStateHash_21, some h.f_prevStateHash_22,
     some h.f_prevStateHash_23, some h.f_prevStateHash_24, some h.f_prevStateHash_25, some h.f_prevStateHash_26, some h.f_prevStateHash_27, some h.f_prevStateHash_28, some h.f_prevStateHash_29, some h.f_prevStateHash_30,
     some h.f_prevStateHash_31, some h.f_postStateHash_0, some h.f_postStateHash_1, some h.f_postStateHash_2, some h.f_postStateHash_3, some h.f_postStateHash_4, some h.f_postStateHash_5, some h.f_postStateHash_6,
     some h.f_postStateHash_7, some h.f_postStateHash_8, some h.f_postStateHash_9, some h.f_postStateHash_10, some h.f_postStateHash_11, some h.f_postStateHash_12, some h.f_postStateHash_13, some h.f_postStateHash_14,
     some h.f_postStateHash_15, some h.f_postStateHash_16, some h.f_postStateHash_17, some h.f_postStateHash_18, some h.f_postStateHash_19, some h.f_postStateHash_20, some h.f_postStateHash_21, some h.f_postStateHash_22,
     some h.f_postStateHash_23, some h.f_postStateHash_24, some h.f_postStateHash_25, some h.f_postStateHash_26, some h.f_postStateHash_27, some h.f_postStateHash_28, some h.f_postStateHash_29, some h.f_postStateHash_30,
     some h.f_postStateHash_31, some h.f_withdrawRootHash_0, some h.f_withdrawRootHash_1, some h.f_withdrawRootHash_2, some h.f_withdrawRootHash_3, some h.f_withdrawRootHash_4, some h.f_withdrawRootHash_5, some h.f_withdrawRootHash_6,
     some h.f_withdrawRootHash_7, some h.f_withdrawRootHash_8, some h.f_withdrawRootHash_9, some h.f_withdrawRootHash_10, some h.f_withdrawRootHash_11, some h.f_withdrawRootHash_12, some h.f_withdrawRootHash_13, some h.f_withdrawRootHash_14,
     some h.f_withdrawRootHash_15, some h.f_withdrawRootHash_16, some h.f_withdrawRootHash_17, some h.f_withdrawRootHash_18, some h.f_withdrawRootHash_19, some h.f_withdrawRootHash_20, some h.f_withdrawRootHash_21, some h.f_withdrawRootHash_22,
     some h.f_withdrawRootHash_23, some h.f_withdrawRootHash_24, some h.f_withdrawRootHash_25, some h.f_withdrawRootHash_26, some h.f_withdrawRootHash_27, some h.f_withdrawRootHash_28, some h.f_withdrawRootHash_29, some h.f_withdrawRootHash_30,
     some h.f_withdrawRootHash_31, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some h.f_parentBatchHash_0, some h.f_parentBatchHash_1, some h.f_parentBatchHash_2, some h.f_parentBatchHash_3, some h.f_parentBatchHash_4, some h.f_parentBatchHash_5, some h.f_parentBatchHash_6,
     some h.f_parentBatchHash_7, some h.f_parentBatchHash_8, some h.f_parentBatchHash_9, some h.f_parentBatchHash_10, some h.f_parentBatchHash_11, some h.f_parentBatchHash_12, some h.f_parentBatchHash_13, some h.f_parentBatchHash_14,
     some h.f_parentBatchHash_15, some h.f_parentBatchHash_16, some h.f_parentBatchHash_17, some h.f_parentBatchHash_18, some h.f_parentBatchHash_19, some h.f_parentBatchHash_20, some h.f_parentBatchHash_21, some h.f_parentBatchHash_22,
     some h.f_parentBatchHash_23, some h.f_parentBatchHash_24, some h.f_parentBatchHash_25, some h.f_parentBatchHash_26, some h.f_parentBatchHash_27, some h.f_parentBatchHash_28, some h.f_parentBatchHash_29, some h.f_parentBatchHash_30,
     some h.f_parentBatchHash_31]
  | 1 =>
    [some h.f_version_0, some h.f_batchIndex_0, some h.f_batchIndex_1, some h.f_batchIndex_2, some h.f_batchIndex_3, some h.f_batchIndex_4, some h.f_batchIndex_5, some h.f_batchIndex_6,
     some h.f_batchIndex_7, some h.f_l1MessagePopped_0, some h.f_l1MessagePopped_1, some h.f_l1MessagePopped_2, some h.f_l1MessagePopped_3, some h.f_l1MessagePopped_4, some h.f_l1MessagePopped_5, some h.f_l1MessagePopped_6,
     some h.f_l1MessagePopped_7, some h.f_totalL1MessagePopped_0, some h.f_totalL1MessagePopped_1, some h.f_totalL1MessagePopped_2, some h.f_totalL1MessagePopped_3, some h.f_totalL1MessagePopped_4, some h.f_totalL1MessagePopped_5, some h.f_totalL1MessagePopped_6,
     some h.f_totalL1MessagePopped_7, some h.f_dataHash_0, some h.f_dataHash_1, some h.f_dataHash_2, some h.f_dataHash_3, some h.f_dataHash_4, some h.f_dataHash_5, some h.f_dataHash_6,
     some h.f_dataHash_7, some h.f_dataHash_8, some h.f_dataHash_9, some h.f_dataHash_10, some h.f_dataHash_11, some h.f_dataHash_12, some h.f_dataHash_13, some h.f_dataHash_14,
     some h.f_dataHash_15, some h.f_dataHash_16, some h.f_dataHash_17, some h.f_dataHash_18, some h.f_dataHash_19, some h.f_dataHash_20, some h.f_dataHash_21, some h.f_dataHash_22,
     some h.f_dataHash_23, some h.f_dataHash_24, some h.f_dataHash_25, some h.f_dataHash_26, some h.f_dataHash_27, some h.f_dataHash_28, some h.f_dataHash_29, some h.f_dataHash_30,
     some h.f_dataHash_31, some h.f_blobVersionedHash_0, some h.f_blobVersionedHash_1, some h.f_blobVersionedHash_2, some h.f_blobVersionedHash_3, some h.f_blobVersionedHash_4, some h.f_blobVersionedHash_5, some h.f_blobVersionedHash_6,
     some h.f_blobVersionedHash_7, some h.f_blobVersionedHash_8, some h.f_blobVersionedHash_9, some h.f_blobVersionedHash_10, some h.f_blobVersionedHash_11, some h.f_blobVersionedHash_12, some h.f_blobVersionedHash_13, some h.f_blobVersionedHash_14,
     some h.f_blobVersionedHash_15, some h.f_blobVersionedHash_16, some h.f_blobVersionedHash_17, some h.f_blobVersionedHash_18, some h.f_blobVersionedHash_19, some h.f_blobVersionedHash_20, some h.f_blobVersionedHash_21, some h.f_blobVersionedHash_22,
     some h.f_blobVersionedHash_23, some h.f_blobVersionedHash_24, some h.f_blobVersionedHash_25, some h.f_blobVersionedHash_26, some h.f_blobVersionedHash_27, some h.f_blobVersionedHash_28, some h.f_blobVersionedHash_29, some h.f_blobVersionedHash_30,
     some h.f_blobVersionedHash_31, some h.f_prevStateHash_0, some h.f_prevStateHash_1, some h.f_prevStateHash_2, some h.f_prevStateHash_3, some h.f_prevStateHash_4, some h.f_prevStateHash_5, some h.f_prevStateHash_6,
     some h.f_prevStateHash_7, some h.f_prevStateHash_8, some h.f_prevStateHash_9, some h.f_prevStateHash_10, some h.f_prevStateHash_11, some h.f_prevStateHash_12, some h.f_prevStateHash_13, some h.f_prevStateHash_14,
     some h.f_prevStateHash_15, some h.f_prevStateHash_16, some h.f_prevStateHash_17, some h.f_prevStateHash_18, some h.f_prevStateHash_19, some h.f_prevStateHash_20, some h.f_prevStateHash_21, some h.f_prevStateHash_22,
     some h.f_prevStateHash_23, some h.f_prevStateHash_24, some h.f_prevStateHash_25, some h.f_prevStateHash_26, some h.f_prevStateHash_27, some h.f_prevStateHash_28, some h.f_prevStateHash_29, some h.f_prevStateHash_30,
     some h.f_prevStateHash_31, some h.f_postStateHash_0, some h.f_postStateHash_1, some h.f_postStateHash_2, some h.f_postStateHash_3, some h.f_postStateHash_4, some h.f_postStateHash_5, some h.f_postStateHash_6,
     some h.f_postStateHash_7, some h.f_postStateHash_8, some h.f_postStateHash_9, some h.f_postStateHash_10, some h.f_postStateHash_11, some h.f_postStateHash_12, some h.f_postStateHash_13, some h.f_postStateHash_14,
     some h.f_postStateHash_15, some h.f_postStateHash_16, some h.f_postStateHash_17, some h.f_postStateHash_18, some h.f_postStateHash_19, some h.f_postStateHash_20, some h.f_postStateHash_21, some h.f_postStateHash_22,
     some h.f_postStateHash_23, some h.f_postStateHash_24, some h.f_postStateHash_25, some h.f_postStateHash_26, some h.f_postStateHash_27, some h.f_postStateHash_28, some h.f_postStateHash_29, some h.f_postStateHash_30,
     some h.f_postStateHash_31, some h.f_withdrawRootHash_0, some h.f_withdrawRootHash_1, some h.f_withdrawRootHash_2, some h.f_withdrawRootHash_3, some h.f_withdrawRootHash_4, some h.f_withdrawRootHash_5, some h.f_withdrawRootHash_6,
     some h.f_withdrawRootHash_7, some h.f_withdrawRootHash_8, some h.f_withdrawRootHash_9, some h.f_withdrawRootHash_10, some h.f_withdrawRootHash_11, some h.f_withdrawRootHash_12, some h.f_withdrawRootHash_13, some h.f_withdrawRootHash_14,
     some h.f_withdrawRootHash_15, some h.f_withdrawRootHash_16, some h.f_withdrawRootHash_17, some h.f_withdrawRootHash_18, some h.f_withdrawRootHash_19, some h.f_withdrawRootHash_20, some h.f_withdrawRootHash_21, some h.f_withdrawRootHash_22,
     some h.f_withdrawRootHash_23, some h.f_withdrawRootHash_24, some h.f_withdrawRootHash_25, some h.f_withdrawRootHash_26, some h.f_withdrawRootHash_27, some h.f_withdrawRootHash_28, some h.f_withdrawRootHash_29, some h.f_withdrawRootHash_30,
     some h.f_withdrawRootHash_31, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some h.f_parentBatchHash_0, some h.f_parentBatchHash_1, some h.f_parentBatchHash_2, some h.f_parentBatchHash_3, some h.f_parentBatchHash_4, some h.f_parentBatchHash_5, some h.f_parentBatchHash_6,
     some h.f_parentBatchHash_7, some h.f_parentBatchHash_8, some h.f_parentBatchHash_9, some h.f_parentBatchHash_10, some h.f_parentBatchHash_11, some h.f_parentBatchHash_12, some h.f_parentBatchHash_13, some h.f_parentBatchHash_14,
     some h.f_parentBatchHash_15, some h.f_parentBatchHash_16, some h.f_parentBatchHash_17, some h.f_parentBatchHash_18, some h.f_parentBatchHash_19, some h.f_parentBatchHash_20, some h.f_parentBatchHash_21, some h.f_parentBatchHash_22,
     some h.f_parentBatchHash_23, some h.f_parentBatchHash_24, some h.f_parentBatchHash_25, some h.f_parentBatchHash_26, some h.f_parentBatchHash_27, some h.f_parentBatchHash_28, some h.f_parentBatchHash_29, some h.f_parentBatchHash_30,
     some h.f_parentBatchHash_31, some h.f_lastBlockNumber_0, some h.f_lastBlockNumber_1, some h.f_lastBlockNumber_2, some h.f_lastBlockNumber_3, some h.f_lastBlockNumber_4, some h.f_lastBlockNumber_5, some h.f_lastBlockNumber_6,
     some h.f_lastBlockNumber_7]
  | 2 =>
    [some h.f_version_0, some h.f_batchIndex_0, some h.f_batchIndex_1, some h.f_batchIndex_2, some h.f_batchIndex_3, some h.f_batchIndex_4, some h.f_batchIndex_5, some h.f_batchIndex_6,
     some h.f_batchIndex_7, some h.f_l1MessagePopped_0, some h.f_l1MessagePopped_1, some h.f_l1MessagePopped_2, some h.f_l1MessagePopped_3, some h.f_l1MessagePopped_4, some h.f_l1MessagePopped_5, some h.f_l1MessagePopped_6,
     some h.f_l1MessagePopped_7, some h.f_totalL1MessagePopped_0, some h.f_totalL1MessagePopped_1, some h.f_totalL1MessagePopped_2, some h.f_totalL1MessagePopped_3, some h.f_totalL1MessagePopped_4, some h.f_totalL1MessagePopped_5, some h.f_totalL1MessagePopped_6,
     some h.f_totalL1MessagePopped_7, some h.f_dataHash_0, some h.f_dataHash_1, some h.f_dataHash_2, some h.f_dataHash_3, some h.f_dataHash_4, some h.f_dataHash_5, some h.f_dataHash_6,
     some h.f_dataHash_7, some h.f_dataHash_8, some h.f_dataHash_9, some h.f_dataHash_10, some h.f_dataHash_11, some h.f_dataHash_12, some h.f_dataHash_13, some h.f_dataHash_14,
     some h.f_dataHash_15, some h.f_dataHash_16, some h.f_dataHash_17, some h.f_dataHash_18, some h.f_dataHash_19, some h.f_dataHash_20, some h.f_dataHash_21, some h.f_dataHash_22,
     some h.f_dataHash_23, some h.f_dataHash_24, some h.f_dataHash_25, some h.f_dataHash_26, some h.f_dataHash_27, some h.f_dataHash_28, some h.f_dataHash_29, some h.f_dataHash_30,
     some h.f_dataHash_31, some h.f_blobVersionedHash_0, some h.f_blobVersionedHash_1, some h.f_blobVersionedHash_2, some h.f_blobVersionedHash_3, some h.f_blobVersionedHash_4, some h.f_blobVersionedHash_5, some h.f_blobVersionedHash_6,
     some h.f_blobVersionedHash_7, some h.f_blobVersionedHash_8, some h.f_blobVersionedHash_9, some h.f_blobVersionedHash_10, some h.f_blobVersionedHash_11, some h.f_blobVersionedHash_12, some h.f_blobVersionedHash_13, some h.f_blobVersionedHash_14,
     some h.f_blobVersionedHash_15, some h.f_blobVersionedHash_16, some h.f_blobVersionedHash_17, some h.f_blobVersionedHash_18, some h.f_blobVersionedHash_19, some h.f_blobVersionedHash_20, some h.f_blobVersionedHash_21, some h.f_blobVersionedHash_22,
     some h.f_blobVersionedHash_23, some h.f_blobVersionedHash_24, some h.f_blobVersionedHash_25, some h.f_blobVersionedHash_26, some h.f_blobVersionedHash_27, some h.f_blobVersionedHash_28, some h.f_blobVersionedHash_29, some h.f_blobVersionedHash_30,
     some h.f_blobVersionedHash_31, some h.f_prevStateHash_0, some h.f_prevStateHash_1, some h.f_prevStateHash_2, some h.f_prevStateHash_3, some h.f_prevStateHash_4, some h.f_prevStateHash_5, some h.f_prevStateHash_6,
     some h.f_prevStateHash_7, some h.f_prevStateHash_8, some h.f_prevStateHash_9, some h.f_prevStateHash_10, some h.f_prevStateHash_11, some h.f_prevStateHash_12, some h.f_prevStateHash_13, some h.f_prevStateHash_14,
     some h.f_prevStateHash_15, some h.f_prevStateHash_16, some h.f_prevStateHash_17, some h.f_prevStateHash_18, some h.f_prevStateHash_19, some h.f_prevStateHash_20, some h.f_prevStateHash_21, some h.f_prevStateHash_22,
     some h.f_prevStateHash_23, some h.f_prevStateHash_24, some h.f_prevStateHash_25, some h.f_prevStateHash_26, some h.f_prevStateHash_27, some h.f_prevStateHash_28, some h.f_prevStateHash_29, some h.f_prevStateHash_30,
     some h.f_prevStateHash_31, some h.f_postStateHash_0, some h.f_postStateHash_1, some h.f_postStateHash_2, some h.f_postStateHash_3, some h.f_postStateHash_4, some h.f_postStateHash_5, some h.f_postStateHash_6,
     some h.f_postStateHash_7, some h.f_postStateHash_8, some h.f_postStateHash_9, some h.f_postStateHash_10, some h.f_postStateHash_11, some h.f_postStateHash_12, some h.f_postStateHash_13, some h.f_postStateHash_14,
     some h.f_postStateHash_15, some h.f_postStateHash_16, some h.f_postStateHash_17, some h.f_postStateHash_18, some h.f_postStateHash_19, some h.f_postStateHash_20, some h.f_postStateHash_21, some h.f_postStateHash_22,
     some h.f_postStateHash_23, some h.f_postStateHash_24, some h.f_postStateHash_25, some h.f_postStateHash_26, some h.f_postStateHash_27, some h.f_postStateHash_28, some h.f_postStateHash_29, some h.f_postStateHash_30,
     some h.f_postStateHash_31, some h.f_withdrawRootHash_0, some h.f_withdrawRootHash_1, some h.f_withdrawRootHash_2, some h.f_withdrawRootHash_3, some h.f_withdrawRootHash_4, some h.f_withdrawRootHash_5, some h.f_withdrawRootHash_6,
     some h.f_withdrawRootHash_7, some h.f_withdrawRootHash_8, some h.f_withdrawRootHash_9, some h.f_withdrawRootHash_10, some h.f_withdrawRootHash_11, some h.f_withdrawRootHash_12, some h.f_withdrawRootHash_13, some h.f_withdrawRootHash_14,
     some h.f_withdrawRootHash_15, some h.f_withdrawRootHash_16, some h.f_withdrawRootHash_17, some h.f_withdrawRootHash_18, some h.f_withdrawRootHash_19, some h.f_withdrawRootHash_20, some h.f_withdrawRootHash_21, some h.f_withdrawRootHash_22,
     some h.f_withdrawRootHash_23, some h.f_withdrawRootHash_24, some h.f_withdrawRootHash_25, some h.f_withdrawRootHash_26, some h.f_withdrawRootHash_27, some h.f_withdrawRootHash_28, some h.f_withdrawRootHash_29, some h.f_withdrawRootHash_30,
     some h.f_withdrawRootHash_31, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00, some 0x00,
     some 0x00, some h.f_parentBatchHash_0, some h.f_parentBatchHash_1, some h.f_parentBatchHash_2, some h.f_parentBatchHash_3, some h.f_parentBatchHash_4, some h.f_parentBatchHash_5, some h.f_parentBatchHash_6,
     some h.f_parentBatchHash_7, some h.f_parentBatchHash_8, some h.f_parentBatchHash_9, some h.f_parentBatchHash_10, some h.f_parentBatchHash_11, some h.f_parentBatchHash_12, some h.f_parentBatchHash_13, some h.f_parentBatchHash_14,
     some h.f_parentBatchHash_15, some h.f_parentBatchHash_16, some h.f_parentBatchHash_17, some h.f_parentBatchHash_18, some h.f_parentBatchHash_19, some h.f_parentBatchHash_20, some h.f_parentBatchHash_21, some h.f_parentBatchHash_22,
     some h.f_parentBatchHash_23, some h.f_parentBatchHash_24, some h.f_parentBatchHash_25, some h.f_parentBatchHash_26, some h.f_parentBatchHash_27, some h.f_parentBatchHash_28, some h.f_parentBatchHash_29, some h.f_parentBatchHash_30,
     some h.f_parentBatchHash_31, some h.f_lastBlockNumber_0, some h.f_lastBlockNumber_1, some h.f_lastBlockNumber_2, some h.f_lastBlockNumber_3, some h.f_lastBlockNumber_4, some h.f_lastBlockNumber_5, some h.f_lastBlockNumber_6,
     some h.f_lastBlockNumber_7]
  | _ => [none]

def c_ok_load_sol (b : Bytes) : Bool :=
  (((Nat.blt 0 (List.length b)) && (Nat.beq (byte_at b 0) 0) && (Nat.ble 249 (List.length b))) ||
    ((Nat.blt 0 (List.length b)) && (!(Nat.beq (byte_at b 0) 0)) && ((Nat.beq (byte_at b 0) 1) || (Nat.beq (byte_at b 0) 2)) && (Nat.beq (List.length b) 257)))

def c_load_sol (b : Bytes) : Option Bytes :=
  sel (c_ok_load_sol b) b

end Model

-- holon:theorems

noncomputable def L_par_dom_BatchHeaderBytes_validate_ok_load_sol_w_b : Model.Bytes :=
  [some 0x00, some 0x26, some 0x4b, some 0x70, some 0x95, some 0xba, some 0xdf, some 0x05,
   some 0x2a, some 0x4f, some 0x74, some 0x99, some 0xbe, some 0xe3, some 0x09, some 0x2e,
   some 0x53, some 0x78, some 0x9d, some 0xc2, some 0xe7, some 0x0d, some 0x32, some 0x57,
   some 0x7c, some 0xa1, some 0xc6, some 0xeb, some 0x11, some 0x36, some 0x5b, some 0x80,
   some 0xa5, some 0xca, some 0xef, some 0x15, some 0x3a, some 0x5f, some 0x84, some 0xa9,
   some 0xce, some 0xf3, some 0x19, some 0x3e, some 0x63, some 0x88, some 0xad, some 0xd2,
   some 0xf7, some 0x1d, some 0x42, some 0x67, some 0x8c, some 0xb1, some 0xd6, some 0xfb,
   some 0x21, some 0x46, some 0x6b, some 0x90, some 0xb5, some 0xda, some 0xff, some 0x25,
   some 0x4a, some 0x6f, some 0x94, some 0xb9, some 0xde, some 0x04, some 0x29, some 0x4e,
   some 0x73, some 0x98, some 0xbd, some 0xe2, some 0x08, some 0x2d, some 0x52, some 0x77,
   some 0x9c, some 0xc1, some 0xe6, some 0x0c, some 0x31, some 0x56, some 0x7b, some 0xa0,
   some 0xc5, some 0xea, some 0x10, some 0x35, some 0x5a, some 0x7f, some 0xa4, some 0xc9,
   some 0xee, some 0x14, some 0x39, some 0x5e, some 0x83, some 0xa8, some 0xcd, some 0xf2,
   some 0x18, some 0x3d, some 0x62, some 0x87, some 0xac, some 0xd1, some 0xf6, some 0x1c,
   some 0x41, some 0x66, some 0x8b, some 0xb0, some 0xd5, some 0xfa, some 0x20, some 0x45,
   some 0x6a, some 0x8f, some 0xb4, some 0xd9, some 0xfe, some 0x24, some 0x49, some 0x6e,
   some 0x93, some 0xb8, some 0xdd, some 0x03, some 0x28, some 0x4d, some 0x72, some 0x97,
   some 0xbc, some 0xe1, some 0x07, some 0x2c, some 0x51, some 0x76, some 0x9b, some 0xc0,
   some 0xe5, some 0x0b, some 0x30, some 0x55, some 0x7a, some 0x9f, some 0xc4, some 0xe9,
   some 0x0f, some 0x34, some 0x59, some 0x7e, some 0xa3, some 0xc8, some 0xed, some 0x13,
   some 0x38, some 0x5d, some 0x82, some 0xa7, some 0xcc, some 0xf1, some 0x17, some 0x3c,
   some 0x61, some 0x86, some 0xab, some 0xd0, some 0xf5, some 0x1b, some 0x40, some 0x65,
   some 0x8a, some 0xaf, some 0xd4, some 0xf9, some 0x1f, some 0x44, some 0x69, some 0x8e,
   some 0xb3, some 0xd8, some 0xfd, some 0x23, some 0x48, some 0x6d, some 0x92, some 0xb7,
   some 0xdc, some 0x02, some 0x27, some 0x4c, some 0x71, some 0x96, some 0xbb, some 0xe0,
   some 0x06, some 0x2b, some 0x50, some 0x75, some 0x9a, some 0xbf, some 0xe4, some 0x0a,
   some 0x2f, some 0x54, some 0x79, some 0x9e, some 0xc3, some 0xe8, some 0x0e, some 0x33,
   some 0x58, some 0x7d, some 0xa2, some 0xc7, some 0xec, some 0x12, some 0x37, some 0x5c,
   some 0x81, some 0xa6, some 0xcb, some 0xf0, some 0x16, some 0x3b, some 0x60, some 0x85,
   some 0xaa, some 0xcf, some 0xf4, some 0x1a, some 0x3f, some 0x64, some 0x89, some 0xae,
   some 0xd3, some 0xf8, some 0x1e, some 0x43, some 0x68, some 0x8d, some 0xb2, some 0xd7,
   some 0xfc, some 0x22]

theorem L_par_dom_BatchHeaderBytes_validate_ok_load_sol_counter : ∃ (v_b : Model.Bytes), Model.c_BatchHeaderBytes_validate v_b ≠ Model.c_ok_load_sol v_b := ⟨L_par_dom_BatchHeaderBytes_validate_ok_load_sol_w_b, by decide⟩

theorem L_par_dom_BatchHeaderBytes_validate_ok_load_sol_refuted : ¬ (∀ (v_b : Model.Bytes), Model.c_BatchHeaderBytes_validate v_b = Model.c_ok_load_sol v_b) := by
  intro H
  obtain ⟨v_b, hne⟩ := L_par_dom_BatchHeaderBytes_validate_ok_load_sol_counter
  exact hne (H v_b)
