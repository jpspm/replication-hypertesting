import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class simpleConditionalAssignmentEqual {

    public static int test(int secret) {
        secret = MultiTainter.taintedInt(secret, "secret_"); // @Phosphor
        int ret;
        ret = 1;
        return ret;
    }

}