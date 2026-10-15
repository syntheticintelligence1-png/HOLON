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

theorem L_par_rt_enc_sol_BatchHeaderBytes_DataHash_v1 : ∀ (v_h : Model.R_Header), ([some v_h.f_version_0] : Model.Bytes) = ([some 0x01] : Model.Bytes) → Model.c_BatchHeaderBytes_DataHash (Model.c_enc_sol v_h) = some ([some v_h.f_dataHash_0, some v_h.f_dataHash_1, some v_h.f_dataHash_2, some v_h.f_dataHash_3, some v_h.f_dataHash_4, some v_h.f_dataHash_5, some v_h.f_dataHash_6, some v_h.f_dataHash_7, some v_h.f_dataHash_8, some v_h.f_dataHash_9, some v_h.f_dataHash_10, some v_h.f_dataHash_11, some v_h.f_dataHash_12, some v_h.f_dataHash_13, some v_h.f_dataHash_14, some v_h.f_dataHash_15, some v_h.f_dataHash_16, some v_h.f_dataHash_17, some v_h.f_dataHash_18, some v_h.f_dataHash_19, some v_h.f_dataHash_20, some v_h.f_dataHash_21, some v_h.f_dataHash_22, some v_h.f_dataHash_23, some v_h.f_dataHash_24, some v_h.f_dataHash_25, some v_h.f_dataHash_26, some v_h.f_dataHash_27, some v_h.f_dataHash_28, some v_h.f_dataHash_29, some v_h.f_dataHash_30, some v_h.f_dataHash_31] : Model.Bytes) := by
  intro v_h p0
  obtain ⟨x0_0, x0_1, x0_2, x0_3, x0_4, x0_5, x0_6, x0_7, x0_8, x0_9, x0_10, x0_11, x0_12, x0_13, x0_14, x0_15, x0_16, x0_17, x0_18, x0_19, x0_20, x0_21, x0_22, x0_23, x0_24, x0_25, x0_26, x0_27, x0_28, x0_29, x0_30, x0_31, x0_32, x0_33, x0_34, x0_35, x0_36, x0_37, x0_38, x0_39, x0_40, x0_41, x0_42, x0_43, x0_44, x0_45, x0_46, x0_47, x0_48, x0_49, x0_50, x0_51, x0_52, x0_53, x0_54, x0_55, x0_56, x0_57, x0_58, x0_59, x0_60, x0_61, x0_62, x0_63, x0_64, x0_65, x0_66, x0_67, x0_68, x0_69, x0_70, x0_71, x0_72, x0_73, x0_74, x0_75, x0_76, x0_77, x0_78, x0_79, x0_80, x0_81, x0_82, x0_83, x0_84, x0_85, x0_86, x0_87, x0_88, x0_89, x0_90, x0_91, x0_92, x0_93, x0_94, x0_95, x0_96, x0_97, x0_98, x0_99, x0_100, x0_101, x0_102, x0_103, x0_104, x0_105, x0_106, x0_107, x0_108, x0_109, x0_110, x0_111, x0_112, x0_113, x0_114, x0_115, x0_116, x0_117, x0_118, x0_119, x0_120, x0_121, x0_122, x0_123, x0_124, x0_125, x0_126, x0_127, x0_128, x0_129, x0_130, x0_131, x0_132, x0_133, x0_134, x0_135, x0_136, x0_137, x0_138, x0_139, x0_140, x0_141, x0_142, x0_143, x0_144, x0_145, x0_146, x0_147, x0_148, x0_149, x0_150, x0_151, x0_152, x0_153, x0_154, x0_155, x0_156, x0_157, x0_158, x0_159, x0_160, x0_161, x0_162, x0_163, x0_164, x0_165, x0_166, x0_167, x0_168, x0_169, x0_170, x0_171, x0_172, x0_173, x0_174, x0_175, x0_176, x0_177, x0_178, x0_179, x0_180, x0_181, x0_182, x0_183, x0_184, x0_185, x0_186, x0_187, x0_188, x0_189, x0_190, x0_191, x0_192, x0_193, x0_194, x0_195, x0_196, x0_197, x0_198, x0_199, x0_200, x0_201, x0_202, x0_203, x0_204, x0_205, x0_206, x0_207, x0_208, x0_209, x0_210, x0_211, x0_212, x0_213, x0_214, x0_215, x0_216, x0_217, x0_218, x0_219, x0_220, x0_221, x0_222, x0_223, x0_224⟩ := v_h
  simp only [List.cons.injEq, Option.some.injEq, and_true] at p0
  obtain rfl := p0
  rfl
