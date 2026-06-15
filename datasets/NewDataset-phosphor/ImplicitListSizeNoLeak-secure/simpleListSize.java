import edu.columbia.cs.psl.phosphor.runtime.MultiTainter; // @Phosphor
import edu.columbia.cs.psl.phosphor.runtime.Taint; // @Phosphor
import java.util.Arrays; // @Phosphor
public class simpleListSize {

    public static int listSizeLeak(int h) {
        h = MultiTainter.taintedInt(h, "h_"); // @Phosphor
        int r = 0;
        int ret;
        if (h < 10) {
            r = 0;
        } else {
            r = 0;
        }
        ret = r;
        return ret;
    }

    public static void main(String[] args) {
        int result = listSizeLeak(5);
        Taint t = MultiTainter.getTaint(result);
        if (t != null) {
            System.out.println("Phosphor: ret is tainted");
            System.out.println("Phosphor: taint labels " + t);
        }
    }

}